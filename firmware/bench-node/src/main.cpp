/*
 * M3 - radar aiming aid.
 *
 * Done condition from HARDWARE_BRINGUP_BRIEF.md: presence flips true/false as
 * you step in and out of range, and distance tracks you.
 *
 * This build is for physically aiming the sensor. It prints one line at 4 Hz
 * with a verdict, so the sensor can be moved while watching the effect instead
 * of guessing at placement.
 *
 * Wire format (established empirically - the module does NOT use the
 * documented Seeed "SY...TC" framing; see firmware/docs/BRINGUP_LOG.md):
 *
 *   uint8  sof = 0x01
 *   uint16 seq          big-endian
 *   uint16 len          big-endian, length of data[] only
 *   uint16 id           big-endian
 *   uint8  token
 *   uint8  data[len]    little-endian words
 *   uint8  checksum     XOR of sof through the last data byte
 *
 * Message ids were confirmed by cross-checking the module's own plain-text log
 * on id 0x0100 against the numeric ids.
 */

#include <Arduino.h>

static constexpr int PIN_LED = LED_BUILTIN;
static constexpr int PIN_RADAR_RX = 44;  // pad D7
static constexpr int PIN_RADAR_TX = 43;  // pad D6
static constexpr uint32_t RADAR_BAUD = 115200;

static constexpr uint8_t SOF = 0x01;
static constexpr size_t MAX_DATA = 64;

// Confirmed message ids.
static constexpr uint16_t ID_LOG = 0x0100;       // ASCII status log
static constexpr uint16_t ID_BREATH = 0x0A14;    // breathing rate, rpm
static constexpr uint16_t ID_HEART = 0x0A15;     // heart rate, bpm
static constexpr uint16_t ID_DISTANCE = 0x0A16;  // target distance, cm
static constexpr uint16_t ID_POSITION = 0x0A17;  // target (x, y), metres
static constexpr uint16_t ID_CLOUD = 0x0A04;     // count + per-target (x, y)
static constexpr uint16_t ID_PRESENCE = 0x0A29;  // presence / target state

// Vitals need a near-stationary subject. The brief gives ~1.5 m for heart rate
// and ~2 m for respiration; below ~30 cm the target sits in the module's own
// near-field clutter.
static constexpr float MIN_USEFUL_CM = 30.0f;
static constexpr float MAX_VITALS_CM = 150.0f;

// Breathing spread over the sample window, above which the reading is not
// trustworthy enough to call locked.
static constexpr float BREATH_SPREAD_LIMIT = 6.0f;

static float last_breath = 0.0f;
static float last_heart = 0.0f;
static float last_distance = 0.0f;
static float last_x = 0.0f, last_y = 0.0f;
static uint32_t last_presence = 0;
static uint32_t last_count = 0;
static char last_log[40] = {0};

static bool have_target = false;
static uint32_t last_target_ms = 0;

// A live person cannot hold a distance to within a hundredth of a centimetre.
// Readings that never move are a rigid reflector - a desk, a wall, the bench
// itself - and every vital derived from them is meaningless. Detect it rather
// than letting a confident-looking number stand.
static float frozen_ref_cm = -1.0f;
static int frozen_samples = 0;
static constexpr float FROZEN_EPS_CM = 0.05f;
static constexpr int FROZEN_LIMIT = 12;  // ~3 s at the 4 Hz report rate

// Rolling window of valid breathing readings, used only to judge stability.
static constexpr int BREATH_WIN = 16;
static float breath_win[BREATH_WIN];
static int breath_n = 0, breath_i = 0;

static uint32_t frames_ok = 0, frames_bad_crc = 0;
static uint32_t last_report = 0;

static float read_f32(const uint8_t *p) {
  float f;
  memcpy(&f, p, 4);
  return f;
}

static uint32_t read_u32(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
         ((uint32_t)p[3] << 24);
}

static int read_byte(uint32_t deadline_ms) {
  while ((int32_t)(millis() - deadline_ms) < 0) {
    if (Serial1.available()) return Serial1.read();
  }
  return -1;
}

void setup() {
  pinMode(PIN_LED, OUTPUT);
  Serial.begin(115200);
  const uint32_t t0 = millis();
  while (!Serial && (millis() - t0) < 3000) delay(50);

  Serial1.begin(RADAR_BAUD, SERIAL_8N1, PIN_RADAR_RX, PIN_RADAR_TX);

  Serial.println();
  Serial.println("=== bench node: M3 radar aiming ===");
  Serial.println();
  Serial.println("Aim the sensor face at your chest, roughly 0.6-1.2 m away,");
  Serial.println("with nothing between you and it. Then sit still.");
  Serial.println();
  Serial.println("Presence and distance work while you move. Breathing and");
  Serial.println("heart rate do not - they need you almost motionless, and are");
  Serial.println("uncalibrated consumer-grade estimates either way.");
  Serial.println();
  last_report = millis();
}

void loop() {
  const int b = read_byte(millis() + 200);
  if (b < 0) return;
  if ((uint8_t)b != SOF) return;

  uint8_t hdr[6];
  const uint32_t deadline = millis() + 100;
  for (int i = 0; i < 6; i++) {
    const int v = read_byte(deadline);
    if (v < 0) return;
    hdr[i] = (uint8_t)v;
  }
  const uint16_t len = ((uint16_t)hdr[2] << 8) | hdr[3];
  const uint16_t id = ((uint16_t)hdr[4] << 8) | hdr[5];
  if (len > MAX_DATA) return;

  const int tok = read_byte(deadline);
  if (tok < 0) return;

  uint8_t data[MAX_DATA];
  for (uint16_t i = 0; i < len; i++) {
    const int v = read_byte(deadline);
    if (v < 0) return;
    data[i] = (uint8_t)v;
  }
  const int crc_rx = read_byte(deadline);
  if (crc_rx < 0) return;

  uint8_t crc = SOF;
  for (int i = 0; i < 6; i++) crc ^= hdr[i];
  crc ^= (uint8_t)tok;
  for (uint16_t i = 0; i < len; i++) crc ^= data[i];
  if (crc != (uint8_t)crc_rx) {
    frames_bad_crc++;
    return;
  }
  frames_ok++;

  switch (id) {
    case ID_BREATH:
      if (len >= 4) {
        last_breath = read_f32(data);
        // The module reports 0 for "no valid estimate". Keeping it out of the
        // window matters: averaging zeros in would manufacture a plausible
        // low reading out of missing data.
        if (last_breath > 0.5f) {
          breath_win[breath_i] = last_breath;
          breath_i = (breath_i + 1) % BREATH_WIN;
          if (breath_n < BREATH_WIN) breath_n++;
        }
      }
      break;
    case ID_HEART:
      if (len >= 4) last_heart = read_f32(data);
      break;
    case ID_DISTANCE:
      if (len >= 8) last_distance = read_f32(data + 4);
      break;
    case ID_POSITION:
      if (len >= 8) {
        last_x = read_f32(data);
        last_y = read_f32(data + 4);
      }
      break;
    case ID_CLOUD:
      if (len >= 4) {
        last_count = read_u32(data);
        if (last_count > 0) {
          have_target = true;
          last_target_ms = millis();
        }
      }
      break;
    case ID_PRESENCE:
      if (len >= 2) last_presence = (uint32_t)(data[0] | (data[1] << 8));
      break;
    case ID_LOG:
      if (len > 0) {
        const uint16_t n = len < sizeof(last_log) - 1 ? len : sizeof(last_log) - 1;
        for (uint16_t k = 0; k < n; k++) {
          const char c = (char)data[k];
          last_log[k] = (c >= 32 && c < 127) ? c : ' ';
        }
        last_log[n] = 0;
      }
      break;
    default:
      break;
  }

  const uint32_t now = millis();
  if (now - last_report < 250) return;
  last_report = now;

  // A target is stale if the cloud has not reported one recently.
  if (now - last_target_ms > 1500) have_target = false;
  digitalWrite(PIN_LED, have_target ? LOW : HIGH);

  float spread = 0.0f;
  if (breath_n >= 4) {
    float lo = breath_win[0], hi = breath_win[0];
    for (int i = 1; i < breath_n; i++) {
      if (breath_win[i] < lo) lo = breath_win[i];
      if (breath_win[i] > hi) hi = breath_win[i];
    }
    spread = hi - lo;
  }

  if (have_target && fabsf(last_distance - frozen_ref_cm) < FROZEN_EPS_CM) {
    if (frozen_samples < 10000) frozen_samples++;
  } else {
    frozen_samples = 0;
    frozen_ref_cm = last_distance;
  }

  const char *verdict;
  if (!have_target) {
    verdict = "NO TARGET - nothing in the beam; aim at your chest";
  } else if (frozen_samples >= FROZEN_LIMIT) {
    verdict = "STATIC REFLECTOR - distance frozen; it is locked on furniture";
  } else if (last_distance < MIN_USEFUL_CM) {
    verdict = "TOO CLOSE - back off past 30 cm";
  } else if (last_distance > MAX_VITALS_CM) {
    verdict = "IN RANGE for presence, TOO FAR for vitals";
  } else if (breath_n < 4) {
    verdict = "TARGET HELD - waiting for a breathing estimate";
  } else if (spread > BREATH_SPREAD_LIMIT) {
    verdict = "UNSTABLE - hold still, or re-aim at the chest";
  } else {
    verdict = "LOCKED";
  }

  Serial.printf(
      "tgt=%lu pres=%lu | dist=%6.1fcm  x=%+5.2f y=%+5.2f | breath=%4.1f "
      "heart=%5.1f | spread=%4.1f | %s\n",
      (unsigned long)last_count, (unsigned long)last_presence, last_distance,
      last_x, last_y, last_breath, last_heart, spread, verdict);
  Serial.printf("    module log: \"%s\"   frames ok=%lu bad=%lu\n", last_log,
                (unsigned long)frames_ok, (unsigned long)frames_bad_crc);
}
