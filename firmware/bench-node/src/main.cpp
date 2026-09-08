/*
 * M4 RX + M5 - unified binary stream.
 *
 * Streams all three modalities to the host over native USB CDC using the
 * length-prefixed frames defined in firmware/shared/frame.h. CSV would not fit
 * at these rates.
 *
 * All three modalities timestamp off the same esp_timer_get_time(). That
 * shared clock is what makes cross-modality alignment possible later, and
 * retrofitting one is painful.
 *
 * CSI rule from the brief: do no processing in the callback. It copies into a
 * ring buffer and returns; the main loop drains it.
 *
 * Radar wire format was established empirically - the module does NOT use the
 * documented Seeed "SY...TC" framing. See firmware/docs/BRINGUP_LOG.md for the
 * derivation and the confirmed message map.
 */

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MLX90640.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

#include "../../shared/frame.h"

// ---------------------------------------------------------------- config ---

static constexpr int PIN_SDA = 5;   // XIAO pad D4
static constexpr int PIN_SCL = 6;   // XIAO pad D5
static constexpr int PIN_RADAR_RX = 44;  // pad D7, confirmed empirically
static constexpr int PIN_RADAR_TX = 43;  // pad D6
static constexpr int PIN_LED = LED_BUILTIN;

static constexpr uint32_t RADAR_BAUD = 115200;

// Must match firmware/tx-node. Nothing works if these disagree, and the
// failure is silent.
static constexpr uint8_t WIFI_CHANNEL = 6;

// ------------------------------------------------------------ csi buffer ---

// Enough subcarriers for HT20 (64 pairs). Anything longer is truncated rather
// than dropped, so a wider capture still yields usable frames.
static constexpr int CSI_MAX_IQ = 128;
static constexpr int CSI_RING = 64;

typedef struct {
  uint64_t t_us;
  int16_t rssi;
  uint16_t n_pairs;
  int8_t iq[CSI_MAX_IQ];
} csi_item_t;

static volatile csi_item_t csi_ring[CSI_RING];
static volatile uint32_t csi_head = 0;  // written by the callback
static volatile uint32_t csi_tail = 0;  // read by the loop
static volatile uint32_t csi_dropped = 0;
static volatile uint32_t csi_total = 0;

// ------------------------------------------------------------------ state ---

static Adafruit_MLX90640 mlx;
static bool mlx_ok = false;
static float thermal_frame[SENSE_THERMAL_PIXELS];

static uint32_t stat_thermal = 0, stat_radar = 0, stat_csi = 0;
static uint32_t last_stat_ms = 0;

// ------------------------------------------------------------- tx framing ---

static uint8_t tx_buf[SENSE_FRAME_HEADER_BYTES + SENSE_FRAME_MAX_PAYLOAD +
                      SENSE_FRAME_CRC_BYTES];

// One writer for every modality, so the wire format lives in exactly one place.
static void send_frame(uint8_t type, uint64_t t_us, const void *payload,
                       uint16_t payload_len) {
  if (payload_len > SENSE_FRAME_MAX_PAYLOAD) return;

  uint8_t *p = tx_buf;
  const uint32_t magic = SENSE_FRAME_MAGIC;
  memcpy(p, &magic, 4);
  p += 4;
  *p++ = type;
  memcpy(p, &t_us, 8);
  p += 8;
  memcpy(p, &payload_len, 2);
  p += 2;
  memcpy(p, payload, payload_len);
  p += payload_len;

  // CRC covers type..payload, i.e. everything but the magic and the CRC.
  const uint16_t crc = sense_crc16(tx_buf + 4, 11 + payload_len);
  memcpy(p, &crc, 2);
  p += 2;

  Serial.write(tx_buf, p - tx_buf);
}

// --------------------------------------------------------------- csi hook ---

// Called from the Wi-Fi task. Copies and returns - nothing else.
static void IRAM_ATTR csi_cb(void *ctx, wifi_csi_info_t *info) {
  (void)ctx;
  if (!info || !info->buf || info->len <= 0) return;

  const uint32_t head = csi_head;
  const uint32_t next = (head + 1) % CSI_RING;
  if (next == csi_tail) {
    csi_dropped++;  // consumer is behind; drop rather than block the radio
    return;
  }

  volatile csi_item_t *slot = &csi_ring[head];
  slot->t_us = (uint64_t)esp_timer_get_time();
  slot->rssi = info->rx_ctrl.rssi;

  int n = info->len;
  if (n > CSI_MAX_IQ) n = CSI_MAX_IQ;
  slot->n_pairs = (uint16_t)(n / 2);
  for (int i = 0; i < n; i++) slot->iq[i] = info->buf[i];

  csi_head = next;
  csi_total++;
}

// Arduino core 2.x signature. The C6 TX node runs a 3.x core, where this takes
// an esp_now_recv_info_t instead - the two nodes deliberately sit on different
// cores, so do not copy this signature across.
static void on_espnow_recv(const uint8_t *mac, const uint8_t *data, int len) {
  (void)mac;
  (void)data;
  (void)len;
  // Reception itself is what triggers the CSI callback; nothing to do here.
}

// ----------------------------------------------------------------- radar ---

static int radar_read(uint32_t deadline_ms) {
  while ((int32_t)(millis() - deadline_ms) < 0) {
    if (Serial1.available()) return Serial1.read();
  }
  return -1;
}

// Latest value per confirmed message id, with an explicit validity flag each.
static float rv_distance_cm = NAN, rv_breath = NAN, rv_heart = NAN;
static float rv_x = NAN, rv_y = NAN;
static uint32_t rv_count = 0, rv_presence = 0;
static bool rv_dirty = false;

static void radar_poll() {
  if (!Serial1.available()) return;
  if ((uint8_t)Serial1.read() != 0x01) return;

  uint8_t hdr[6];
  const uint32_t deadline = millis() + 30;
  for (int i = 0; i < 6; i++) {
    const int v = radar_read(deadline);
    if (v < 0) return;
    hdr[i] = (uint8_t)v;
  }
  const uint16_t len = ((uint16_t)hdr[2] << 8) | hdr[3];
  const uint16_t id = ((uint16_t)hdr[4] << 8) | hdr[5];
  if (len > 64) return;

  const int tok = radar_read(deadline);
  if (tok < 0) return;
  uint8_t data[64];
  for (uint16_t i = 0; i < len; i++) {
    const int v = radar_read(deadline);
    if (v < 0) return;
    data[i] = (uint8_t)v;
  }
  const int crc_rx = radar_read(deadline);
  if (crc_rx < 0) return;

  uint8_t crc = 0x01;
  for (int i = 0; i < 6; i++) crc ^= hdr[i];
  crc ^= (uint8_t)tok;
  for (uint16_t i = 0; i < len; i++) crc ^= data[i];
  if (crc != (uint8_t)crc_rx) return;

  float f;
  switch (id) {
    case 0x0A14:  // breathing rate, rpm
      if (len >= 4) {
        memcpy(&f, data, 4);
        // 0 is the module's "no valid estimate" marker, not a measurement.
        rv_breath = (f > 0.5f) ? f : NAN;
        rv_dirty = true;
      }
      break;
    case 0x0A15:  // heart rate, bpm
      if (len >= 4) {
        memcpy(&f, data, 4);
        rv_heart = (f > 0.5f) ? f : NAN;
        rv_dirty = true;
      }
      break;
    case 0x0A16:  // target distance, cm
      if (len >= 8) {
        memcpy(&f, data + 4, 4);
        rv_distance_cm = f;
        rv_dirty = true;
      }
      break;
    case 0x0A17:  // target position, metres
      if (len >= 8) {
        memcpy(&rv_x, data, 4);
        memcpy(&rv_y, data + 4, 4);
        rv_dirty = true;
      }
      break;
    case 0x0A04:  // point cloud: target count first
      if (len >= 4) {
        rv_count = (uint32_t)data[0] | ((uint32_t)data[1] << 8) |
                   ((uint32_t)data[2] << 16) | ((uint32_t)data[3] << 24);
        rv_dirty = true;
      }
      break;
    case 0x0A29:  // presence / target state
      if (len >= 2) {
        rv_presence = (uint32_t)(data[0] | (data[1] << 8));
        rv_dirty = true;
      }
      break;
    default:
      break;
  }
}

static void emit_radar() {
  if (!rv_dirty) return;
  rv_dirty = false;

  sense_radar_payload_t pl;
  pl.valid = 0;
  pl.presence = SENSE_RADAR_PRESENCE_ABSENT;
  pl.quality = SENSE_RADAR_QUALITY_ABSENT;
  pl.distance_m = NAN;
  pl.respiration_rpm = NAN;
  pl.heart_rate_bpm = NAN;

  // Presence gates everything else. With no target the module still reports a
  // distance of 0.0, which is not a measurement of anything - forwarding it
  // would put a confident "0.00 m" on the dashboard for an empty room. The
  // contract's rule against zero-filling applies to a zero the sensor itself
  // volunteers, not just to one we would invent.
  const bool target = rv_count > 0;

  pl.valid |= SENSE_RADAR_VALID_PRESENCE;
  pl.presence = target ? 1 : 0;

  if (target) {
    if (!isnan(rv_distance_cm) && rv_distance_cm > 1.0f) {
      pl.valid |= SENSE_RADAR_VALID_DISTANCE;
      pl.distance_m = rv_distance_cm / 100.0f;
    }
    if (!isnan(rv_breath)) {
      pl.valid |= SENSE_RADAR_VALID_RESPIRATION;
      pl.respiration_rpm = rv_breath;
    }
    if (!isnan(rv_heart)) {
      pl.valid |= SENSE_RADAR_VALID_HEART_RATE;
      pl.heart_rate_bpm = rv_heart;
    }
  } else {
    // Drop stale vitals rather than letting the last live reading linger after
    // the person leaves.
    rv_breath = rv_heart = NAN;
  }

  send_frame(SENSE_FRAME_RADAR, (uint64_t)esp_timer_get_time(), &pl, sizeof(pl));
  stat_radar++;
}

// ------------------------------------------------------------------ setup ---

void setup() {
  pinMode(PIN_LED, OUTPUT);
  Serial.begin(115200);
  const uint32_t t0 = millis();
  while (!Serial && (millis() - t0) < 3000) delay(50);

  Wire.begin(PIN_SDA, PIN_SCL, 1000000);
  if (mlx.begin(MLX90640_I2CADDR_DEFAULT, &Wire)) {
    mlx.setMode(MLX90640_CHESS);
    mlx.setResolution(MLX90640_ADC_18BIT);
    mlx.setRefreshRate(MLX90640_16_HZ);
    mlx_ok = true;
  }

  Serial1.begin(RADAR_BAUD, SERIAL_8N1, PIN_RADAR_RX, PIN_RADAR_TX);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  esp_wifi_set_ps(WIFI_PS_NONE);
  esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);

  if (esp_now_init() == ESP_OK) {
    esp_now_register_recv_cb(on_espnow_recv);
  }

  // CSI delivers nothing in plain STA mode: the driver discards frames that
  // are not addressed to this station before they reach the CSI stage.
  // Measured directly - 0 callbacks against 1460 ESP-NOW receptions in the
  // same 3 s window, then callbacks immediately on enabling promiscuous mode.
  // Filter to data frames so ambient management traffic does not dilute the
  // stream with beacons from every AP in range.
  wifi_promiscuous_filter_t promisc_filter = {};
  promisc_filter.filter_mask = WIFI_PROMIS_FILTER_MASK_DATA;
  esp_wifi_set_promiscuous_filter(&promisc_filter);
  esp_wifi_set_promiscuous(true);

  wifi_csi_config_t csi_cfg = {};
  csi_cfg.lltf_en = true;
  csi_cfg.htltf_en = true;
  csi_cfg.stbc_htltf2_en = false;
  csi_cfg.ltf_merge_en = true;
  csi_cfg.channel_filter_en = true;
  csi_cfg.manu_scale = false;
  csi_cfg.shift = 0;
  esp_wifi_set_csi_config(&csi_cfg);
  esp_wifi_set_csi_rx_cb(csi_cb, NULL);
  esp_wifi_set_csi(true);

  last_stat_ms = millis();
}

// ------------------------------------------------------------------- loop ---

void loop() {
  // Drain the CSI ring first; it is the highest-rate producer.
  int drained = 0;
  while (csi_tail != csi_head && drained < 32) {
    volatile csi_item_t *slot = &csi_ring[csi_tail];

    uint8_t pl[4 + CSI_MAX_IQ];
    const int16_t rssi = slot->rssi;
    const uint16_t n = slot->n_pairs;
    memcpy(pl, &rssi, 2);
    memcpy(pl + 2, &n, 2);
    const int nbytes = n * 2;
    for (int i = 0; i < nbytes; i++) pl[4 + i] = (uint8_t)slot->iq[i];

    send_frame(SENSE_FRAME_CSI, slot->t_us, pl, (uint16_t)(4 + nbytes));
    csi_tail = (csi_tail + 1) % CSI_RING;
    stat_csi++;
    drained++;
  }

  radar_poll();
  emit_radar();

  if (mlx_ok && mlx.getFrame(thermal_frame) == 0) {
    send_frame(SENSE_FRAME_THERMAL, (uint64_t)esp_timer_get_time(),
               thermal_frame, sizeof(thermal_frame));
    stat_thermal++;
    digitalWrite(PIN_LED, (stat_thermal & 1) ? LOW : HIGH);
  }

  // Counters ride in a radar-shaped frame? No - they would pollute the data.
  // Rates are derived host-side from frame arrival times instead, so the
  // stream carries only measurements.
  const uint32_t now = millis();
  if (now - last_stat_ms >= 5000) {
    last_stat_ms = now;
    stat_thermal = stat_radar = stat_csi = 0;
  }
}
