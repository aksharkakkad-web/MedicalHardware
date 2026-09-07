/*
 * M3 - radar decode.
 *
 * Done condition from HARDWARE_BRINGUP_BRIEF.md: presence flips true/false as
 * you step in and out of range, and distance tracks you.
 *
 * UART pins were established empirically, not guessed: GPIO44 (pad D7) carries
 * traffic and GPIO43 (pad D6) is silent. These are the classic UART0 pins,
 * which is only safe because the host link is native USB CDC.
 *
 * The wire format is NOT the "SY...TC" Seeed 60 GHz framing. Observed and
 * confirmed against an XOR checksum over several hundred frames:
 *
 *   uint8  sof   = 0x01
 *   uint16 seq          big-endian, increments once per message
 *   uint16 len          big-endian, length of data[] only
 *   uint16 id           big-endian message id
 *   uint8  token
 *   uint8  data[len]
 *   uint8  checksum     XOR of every byte from sof through the last data byte
 *
 * Message semantics are deliberately NOT hard-coded to a guess. Each id is
 * decoded structurally (u16/u32/float32 little-endian) and printed with its
 * update rate, so stepping in and out of range is what identifies presence and
 * distance. Assigning meaning before observing it is how a bring-up ends up
 * reporting a constant as a vital sign.
 */

#include <Arduino.h>

static constexpr int PIN_LED = LED_BUILTIN;
static constexpr int PIN_RADAR_RX = 44;  // pad D7
static constexpr int PIN_RADAR_TX = 43;  // pad D6
static constexpr uint32_t RADAR_BAUD = 115200;

static constexpr uint8_t SOF = 0x01;
static constexpr size_t MAX_DATA = 64;
static constexpr int MAX_IDS = 16;

struct IdSlot {
  uint16_t id;
  uint32_t count;
  uint32_t count_at_last_report;
  uint16_t len;
  uint8_t data[MAX_DATA];
};

static IdSlot slots[MAX_IDS];
static int n_slots = 0;

static uint32_t frames_ok = 0;
static uint32_t frames_bad_crc = 0;
static uint32_t resyncs = 0;
static uint32_t last_report = 0;

static IdSlot *slot_for(uint16_t id) {
  for (int i = 0; i < n_slots; i++) {
    if (slots[i].id == id) return &slots[i];
  }
  if (n_slots >= MAX_IDS) return nullptr;
  IdSlot *s = &slots[n_slots++];
  s->id = id;
  s->count = 0;
  s->count_at_last_report = 0;
  s->len = 0;
  return s;
}

static float read_f32(const uint8_t *p) {
  float f;
  memcpy(&f, p, 4);  // little-endian payload, matching the MCU
  return f;
}

// Blocking read of one byte with a deadline, so a stalled link cannot wedge
// the parser.
static int read_byte(uint32_t deadline_ms) {
  while (millis() < deadline_ms) {
    if (Serial1.available()) return Serial1.read();
  }
  return -1;
}

void setup() {
  pinMode(PIN_LED, OUTPUT);
  Serial.begin(115200);
  const uint32_t wait_start = millis();
  while (!Serial && (millis() - wait_start) < 3000) delay(50);

  Serial1.begin(RADAR_BAUD, SERIAL_8N1, PIN_RADAR_RX, PIN_RADAR_TX);

  Serial.println();
  Serial.println("=== bench node: M3 radar decode ===");
  Serial.printf("uart : RX=GPIO%d (D7), TX=GPIO%d (D6) @ %lu 8N1\n",
                PIN_RADAR_RX, PIN_RADAR_TX, (unsigned long)RADAR_BAUD);
  Serial.println();
  Serial.println("Step in and out of range. Watch which id flips and which");
  Serial.println("tracks your distance - that is what identifies them.");
  Serial.println();
  last_report = millis();
}

void loop() {
  // --- frame sync ---
  const int b = read_byte(millis() + 200);
  if (b < 0) return;
  if ((uint8_t)b != SOF) {
    resyncs++;
    return;
  }

  uint8_t hdr[6];
  const uint32_t deadline = millis() + 100;
  for (int i = 0; i < 6; i++) {
    const int v = read_byte(deadline);
    if (v < 0) return;
    hdr[i] = (uint8_t)v;
  }

  const uint16_t seq = ((uint16_t)hdr[0] << 8) | hdr[1];
  const uint16_t len = ((uint16_t)hdr[2] << 8) | hdr[3];
  const uint16_t id = ((uint16_t)hdr[4] << 8) | hdr[5];
  (void)seq;

  if (len > MAX_DATA) {
    resyncs++;
    return;
  }

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
  digitalWrite(PIN_LED, (frames_ok & 8) ? HIGH : LOW);

  IdSlot *s = slot_for(id);
  if (s) {
    s->count++;
    s->len = len;
    memcpy(s->data, data, len);
  }

  // --- 1 Hz report ---
  const uint32_t now = millis();
  if (now - last_report < 1000) return;
  const float elapsed = (now - last_report) / 1000.0f;
  last_report = now;

  Serial.printf("frames ok=%lu  bad_crc=%lu  resync=%lu\n",
                (unsigned long)frames_ok, (unsigned long)frames_bad_crc,
                (unsigned long)resyncs);

  for (int i = 0; i < n_slots; i++) {
    IdSlot *slot = &slots[i];
    const float hz = (slot->count - slot->count_at_last_report) / elapsed;
    slot->count_at_last_report = slot->count;

    Serial.printf("  id 0x%04X  %5.1f Hz  len %2u  ", slot->id, hz, slot->len);

    // Message 0x0100 carries the module's own plain-text status log. It is
    // the most reliable source of field semantics available, since the
    // firmware is not customizable and no register map ships with the part.
    if (slot->id == 0x0100) {
      Serial.print('"');
      for (uint16_t k = 0; k < slot->len; k++) {
        const char c = (char)slot->data[k];
        Serial.print((c >= 32 && c < 127) ? c : '.');
      }
      Serial.print('"');
    } else if (slot->len == 2) {
      Serial.printf("u16=%u", (unsigned)(slot->data[0] | (slot->data[1] << 8)));
    } else if (slot->len >= 4 && slot->len % 4 == 0) {
      const int n_words = slot->len / 4;
      for (int w = 0; w < n_words && w < 6; w++) {
        const uint8_t *p = slot->data + w * 4;
        const uint32_t u = (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
                           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
        const float f = read_f32(p);
        // A word that is a small integer is almost certainly a count or flag;
        // anything else is shown as a float.
        if (u <= 1000) {
          Serial.printf("[%lu] ", (unsigned long)u);
        } else {
          Serial.printf("%.3f ", f);
        }
      }
    } else {
      for (uint16_t k = 0; k < slot->len && k < 12; k++) {
        Serial.printf("%02X ", slot->data[k]);
      }
    }
    Serial.println();
  }
  Serial.println();
}
