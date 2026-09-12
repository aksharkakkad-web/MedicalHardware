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

// Accept CSI only from the TX node.
//
// Promiscuous capture picks up every AP in range, so the stream was a mixture:
// the beacon at about -50 dBm interleaved with ambient traffic at about -90.
// Those are different transmitters over different paths, and interleaving them
// destroys the temporal coherence that breathing and movement estimation
// depend on - consecutive samples were not measuring the same channel. One
// source, one path, one coherent time series.
static const uint8_t TX_NODE_MAC[6] = {0x10, 0xBD, 0xA3, 0x96, 0x47, 0xD8};
static constexpr bool CSI_FILTER_BY_MAC = true;

// ------------------------------------------------------------ csi buffer ---

// Enough subcarriers for HT20 (64 pairs). Anything longer is truncated rather
// than dropped, so a wider capture still yields usable frames.
// Stream one CSI frame in N. Capture still runs at the full beacon rate and
// the true rate is reported in the stats frame; this only limits what crosses
// USB.
//
// At 500 Hz, CSI alone is ~75 KB/s and it starved everything else: thermal
// fell to 1 Hz, radar to 17 Hz, and CRC errors began climbing as writes were
// truncated. Nothing downstream needs that rate. The vitals estimator
// decimates to 25 Hz internally, and breathing at 0.1-0.5 Hz and cardiac at
// 0.8-2.0 Hz are nowhere near Nyquist-limited by 100 Hz. The 500 Hz figure in
// the brief was for gait Doppler, which is out of scope.
static constexpr uint32_t CSI_STREAM_DIVISOR = 5;  // 500 Hz captured -> 100 Hz streamed

static constexpr int CSI_MAX_IQ = 128;
static constexpr int CSI_RING = 256;

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
static volatile uint32_t csi_rejected = 0;

// ------------------------------------------------------------------ state ---

static Adafruit_MLX90640 mlx;
static bool mlx_ok = false;
static float thermal_frame[SENSE_THERMAL_PIXELS];

// Enabling MGMT+DATA promiscuous capture stopped thermal frames dead: read
// rate went 7.8 Hz -> 0 while the loop sped up, i.e. getFrame() began failing
// immediately rather than blocking. This is the I2C-under-Wi-Fi-load contention
// the bring-up brief warns about in section 6. Recover the bus instead of
// silently reporting no thermal data.
// Defined below, but needed by thermal_recover(): a bus reset has to bring the
// light sensor back up too, since both sit on the same I2C bus.
static bool bh1750_begin();
static bool lux_ok;

static uint32_t mlx_fail_streak = 0;
static uint32_t mlx_recoveries = 0;
static uint32_t last_reported_recoveries = 0;
static constexpr uint32_t MLX_FAIL_LIMIT = 8;

static void thermal_recover() {
  mlx_recoveries++;
  mlx_fail_streak = 0;
  Wire.end();
  delay(5);
  // 400 kHz rather than 1 MHz. The faster clock sustains 16 Hz in a quiet
  // system but has far less margin once the radio is saturating the bus with
  // interrupts; frames at 8 Hz are worth more than frames at 16 Hz that stop.
  // 1 MHz. The bus was dropped to 400 kHz when thermal died under Wi-Fi load,
  // before the recovery path existed. With recovery in place the faster clock
  // is worth taking back: getFrame() duration is what drags the loop down, and
  // at 400 kHz reading 768 pixels twice per frame was holding the loop near
  // 1 Hz. A failed transaction now re-inits the bus instead of killing the
  // stream.
  Wire.begin(PIN_SDA, PIN_SCL, 1000000);
  mlx_ok = mlx.begin(MLX90640_I2CADDR_DEFAULT, &Wire);
  if (mlx_ok) {
    mlx.setMode(MLX90640_CHESS);
    mlx.setResolution(MLX90640_ADC_18BIT);
    mlx.setRefreshRate(MLX90640_16_HZ);
  }
  lux_ok = bh1750_begin();
}

// BH1750 on the carrier, same bus as the thermal sensor. Driven directly -
// it is two registers and a 16-bit read, which is less code than a dependency.
static constexpr uint8_t BH1750_ADDR = 0x23;
static constexpr uint8_t BH1750_POWER_ON = 0x01;
static constexpr uint8_t BH1750_CONT_HIRES = 0x10;
static uint32_t last_lux_ms = 0;

static bool bh1750_begin() {
  Wire.beginTransmission(BH1750_ADDR);
  Wire.write(BH1750_POWER_ON);
  if (Wire.endTransmission() != 0) return false;
  Wire.beginTransmission(BH1750_ADDR);
  Wire.write(BH1750_CONT_HIRES);
  return Wire.endTransmission() == 0;
}

// Returns NaN when the sensor does not answer. Never 0 - a dark room is a
// legitimate 0 lux, so zero cannot also mean "no reading".
static float bh1750_read() {
  if (Wire.requestFrom((uint8_t)BH1750_ADDR, (uint8_t)2) != 2) return NAN;
  const uint16_t raw = ((uint16_t)Wire.read() << 8) | Wire.read();
  return raw / 1.2f;
}

static uint32_t stat_thermal = 0, stat_radar = 0, stat_csi = 0;
static uint32_t last_stat_ms = 0;

// ------------------------------------------------------------- tx framing ---

// Two tasks now write frames - the sensor loop on core 1 and the CSI drain on
// core 0 - so the buffer and the USB write have to be serialised.
static SemaphoreHandle_t tx_mutex = nullptr;

static void send_frame(uint8_t type, uint64_t t_us, const void *payload,
                       uint16_t payload_len) {
  if (payload_len > SENSE_FRAME_MAX_PAYLOAD) return;
  // At 500 Hz the CSI drain wants this mutex almost continuously. A short
  // timeout meant the thermal frame simply gave up and was discarded, which
  // showed as thermal collapsing to 0.7 Hz while CSI ran perfectly. Wait long
  // enough that a slow producer still gets its turn.
  if (tx_mutex && xSemaphoreTake(tx_mutex, pdMS_TO_TICKS(400)) != pdTRUE) return;

  static uint8_t tx_buf[SENSE_FRAME_HEADER_BYTES + SENSE_FRAME_MAX_PAYLOAD +
                        SENSE_FRAME_CRC_BYTES];
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

  // USB CDC accepts short writes when its buffer is full. Returning early
  // leaves a truncated frame on the wire, and the next task's frame lands in
  // the middle of it - which is exactly the CRC errors and resyncs that
  // appeared when the CSI drain moved to its own core.
  const size_t total = (size_t)(p - tx_buf);
  size_t sent = 0;
  uint32_t guard = 0;
  while (sent < total && guard++ < 2000) {
    const size_t n = Serial.write(tx_buf + sent, total - sent);
    if (n == 0) {
      delayMicroseconds(200);
    } else {
      sent += n;
    }
  }
  if (tx_mutex) xSemaphoreGive(tx_mutex);
}

/*
 * CSI drain, pinned to core 0.
 *
 * The brief says to drain the ring on the other core, and skipping that turned
 * out to matter: with the drain inline in loop(), thermal and CSI could not
 * both run. mlx.getFrame() blocks for over 100 ms, and during that window the
 * 64-entry ring overflows and the callback drops everything. Measured as
 * 12.5 Hz CSI with thermal dead, or 7.8 Hz thermal with CSI dead, depending on
 * which side won.
 */
static void csi_drain_task(void *arg) {
  (void)arg;
  for (;;) {
    int drained = 0;
    // Bounded per pass so the mutex is released regularly rather than held
    // across a long burst.
    while (csi_tail != csi_head && drained < 16) {
      volatile csi_item_t *slot = &csi_ring[csi_tail];

      static uint32_t seen = 0;
      if ((seen++ % CSI_STREAM_DIVISOR) != 0) {
        csi_tail = (csi_tail + 1) % CSI_RING;
        drained++;
        continue;
      }

      uint8_t pl[4 + CSI_MAX_IQ];
      const int16_t rssi = slot->rssi;
      const uint16_t n = slot->n_pairs;
      const uint64_t t_us = slot->t_us;
      memcpy(pl, &rssi, 2);
      memcpy(pl + 2, &n, 2);
      const int nbytes = n * 2;
      for (int i = 0; i < nbytes; i++) pl[4 + i] = (uint8_t)slot->iq[i];

      csi_tail = (csi_tail + 1) % CSI_RING;
      send_frame(SENSE_FRAME_CSI, t_us, pl, (uint16_t)(4 + nbytes));
      stat_csi++;
      drained++;
    }
    vTaskDelay(pdMS_TO_TICKS(2));
  }
}

// --------------------------------------------------------------- csi hook ---

// Called from the Wi-Fi task. Copies and returns - nothing else.
static void IRAM_ATTR csi_cb(void *ctx, wifi_csi_info_t *info) {
  (void)ctx;
  if (!info || !info->buf || info->len <= 0) return;

  if (CSI_FILTER_BY_MAC) {
    for (int i = 0; i < 6; i++) {
      if (info->mac[i] != TX_NODE_MAC[i]) {
        csi_rejected++;
        return;
      }
    }
  }

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
static volatile uint32_t espnow_rx = 0;

static void on_espnow_recv(const uint8_t *mac, const uint8_t *data, int len) {
  espnow_rx++;
  (void)mac;
  (void)data;
  (void)len;
  // Reception itself is what triggers the CSI callback; nothing to do here.
}

// ----------------------------------------------------------------- radar ---

/*
 * No decoding here. Bytes are drained from the UART and forwarded verbatim as
 * SENSE_FRAME_RADAR_RAW; the host reassembles the vendor protocol.
 *
 * The previous version parsed frames inline in loop(), using blocking reads
 * with deadlines. Sharing that loop with a thermal read that blocks for over
 * 100 ms starved the radar to 0.7 Hz. Draining on its own task, with a UART
 * buffer deep enough to cover a thermal read, removes the coupling entirely.
 */
static void radar_task(void *arg) {
  (void)arg;
  static uint8_t chunk[256];
  for (;;) {
    size_t n = 0;
    while (Serial1.available() && n < sizeof(chunk)) {
      chunk[n++] = (uint8_t)Serial1.read();
    }
    if (n > 0) {
      send_frame(SENSE_FRAME_RADAR_RAW, (uint64_t)esp_timer_get_time(), chunk,
                 (uint16_t)n);
      stat_radar++;
    }
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}

// ------------------------------------------------------------------ setup ---

void setup() {
  pinMode(PIN_LED, OUTPUT);
  Serial.begin(115200);
  const uint32_t t0 = millis();
  while (!Serial && (millis() - t0) < 3000) delay(50);

  // 1 MHz. The bus was dropped to 400 kHz when thermal died under Wi-Fi load,
  // before the recovery path existed. With recovery in place the faster clock
  // is worth taking back: getFrame() duration is what drags the loop down, and
  // at 400 kHz reading 768 pixels twice per frame was holding the loop near
  // 1 Hz. A failed transaction now re-inits the bus instead of killing the
  // stream.
  Wire.begin(PIN_SDA, PIN_SCL, 1000000);
  if (mlx.begin(MLX90640_I2CADDR_DEFAULT, &Wire)) {
    mlx.setMode(MLX90640_CHESS);
    mlx.setResolution(MLX90640_ADC_18BIT);
    mlx.setRefreshRate(MLX90640_16_HZ);
    mlx_ok = true;
  }

  lux_ok = bh1750_begin();

  // 115200 baud fills the default 128-byte FIFO in about 11 ms, far less than
  // one thermal read. A deeper buffer means nothing is lost while the other
  // core is busy.
  Serial1.setRxBufferSize(4096);
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
  // MGMT *and* DATA. Measured here: DATA-only collapsed the yield to 1.4 Hz
  // because most CSI-bearing traffic on a quiet channel is beacons. The
  // ruvnet/ruview project reports the same effect from the other direction -
  // MGMT-only starves display-less boards to 0 pps.
  //
  // Their firmware warns that DATA promiscuous at 100-500 interrupts/sec can
  // crash Core 0 in wDev_ProcessFiq via a flash-cache race in the Wi-Fi blob.
  // Not observed here on Arduino core 2.x, but it is the first thing to
  // suspect if this node starts resetting under load.
  wifi_promiscuous_filter_t promisc_filter = {};
  promisc_filter.filter_mask =
      WIFI_PROMIS_FILTER_MASK_MGMT | WIFI_PROMIS_FILTER_MASK_DATA;
  esp_wifi_set_promiscuous_filter(&promisc_filter);
  esp_wifi_set_promiscuous(true);

  wifi_csi_config_t csi_cfg = {};
  csi_cfg.lltf_en = true;
  csi_cfg.htltf_en = true;
  // Sample the second HT-LTF under STBC, and do not let the channel filter
  // discard estimates - both widen what actually reaches the callback.
  csi_cfg.stbc_htltf2_en = true;
  csi_cfg.ltf_merge_en = true;
  csi_cfg.channel_filter_en = false;
  csi_cfg.manu_scale = false;
  csi_cfg.shift = 0;
  esp_wifi_set_csi_config(&csi_cfg);
  esp_wifi_set_csi_rx_cb(csi_cb, NULL);
  esp_wifi_set_csi(true);

  tx_mutex = xSemaphoreCreateMutex();

  // Core 0 alongside the Wi-Fi driver; the sensor loop keeps core 1.
  // Priority 2, not 6. The Arduino loop task that owns thermal runs at 1, so a
  // high-priority drain starved it outright. CSI still keeps up at 500 Hz
  // because it is I/O bound on USB, not CPU bound.
  xTaskCreatePinnedToCore(csi_drain_task, "csi_drain", 4096, nullptr, 2, nullptr, 0);
  xTaskCreatePinnedToCore(radar_task, "radar", 3072, nullptr, 4, nullptr, 0);

  last_stat_ms = millis();
}

// ------------------------------------------------------------------- loop ---

void loop() {
  // Thermal and light share this loop deliberately. Wire is not thread-safe,
  // and putting the BH1750 on its own task let it interleave with a thermal
  // read mid-transaction - which killed thermal outright while the light
  // sensor kept reporting. Both I2C devices are therefore driven from one
  // thread. CSI and radar have no bus to contend for and stay on their own
  // tasks.
  static uint32_t last_stats = 0;
  if (millis() - last_stats >= 1000) {
    last_stats = millis();
    sense_stats_payload_t st;
    st.csi_accepted = csi_total;
    st.csi_rejected = csi_rejected;
    st.csi_dropped = csi_dropped;
    st.espnow_rx = espnow_rx;
    st.thermal_recoveries = mlx_recoveries;
    send_frame(SENSE_FRAME_STATS, (uint64_t)esp_timer_get_time(), &st, sizeof(st));
  }

  static uint32_t last_lux = 0;
  if (millis() - last_lux >= 500) {
    last_lux = millis();
    sense_ambient_payload_t amb;
    const float lux = lux_ok ? bh1750_read() : NAN;
    amb.valid = isnan(lux) ? 0 : 1;
    amb.lux = lux;
    send_frame(SENSE_FRAME_AMBIENT, (uint64_t)esp_timer_get_time(), &amb,
               sizeof(amb));
  }

  if (mlx_ok) {
    if (mlx.getFrame(thermal_frame) == 0) {
      mlx_fail_streak = 0;
      send_frame(SENSE_FRAME_THERMAL, (uint64_t)esp_timer_get_time(),
                 thermal_frame, sizeof(thermal_frame));
      stat_thermal++;
      digitalWrite(PIN_LED, (stat_thermal & 1) ? LOW : HIGH);
    } else if (++mlx_fail_streak >= MLX_FAIL_LIMIT) {
      thermal_recover();
    }
  } else {
    delay(20);
  }
}
