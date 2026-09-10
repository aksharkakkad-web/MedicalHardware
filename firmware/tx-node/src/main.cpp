/*
 * M4 TX + remote CSI - Seeed XIAO ESP32-C6.
 *
 * Two jobs:
 *   1. Broadcast at a steady 500 Hz so the bench node can measure CSI.
 *   2. Capture CSI here as well and relay it to the bench node.
 *
 * On (1): the beacon now forces an OFDM/HT rate. ESP-NOW broadcast otherwise
 * defaults to a basic 802.11b rate, which carries no HT-LTF and yields no
 * usable channel estimate - measured as CSI arriving at RSSI -91 (distant
 * ambient traffic) while this node sat at -50 in the same room.
 *
 * On (2): this is worth doing because the C6 stands somewhere else in the
 * room, so ambient traffic reaches it along a different path than it reaches
 * the S3. Measuring the C6<->S3 link from both ends would only give two looks
 * at one path, since the channel is reciprocal.
 *
 * No analysis happens here. The CSI callback copies and returns; the relay
 * task forwards raw I/Q. All interpretation is on the host.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

static constexpr uint8_t WIFI_CHANNEL = 6;      // must match the bench node
static constexpr uint32_t TX_INTERVAL_US = 2000; // 500 Hz

// Relay far below capture rate. ESP-NOW airtime spent relaying is airtime not
// spent beaconing, and the beacon is what the bench node measures.
static constexpr uint32_t RELAY_INTERVAL_MS = 40;  // ~25 Hz

static constexpr int PIN_LED = LED_BUILTIN;
static uint8_t BROADCAST_MAC[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// First byte tags the packet so the bench node can tell a beacon from a relay.
static constexpr uint8_t MSG_BEACON = 1;
static constexpr uint8_t MSG_CSI = 2;

typedef struct __attribute__((packed)) {
  uint8_t kind;
  uint32_t seq;
  uint32_t t_us;
} beacon_t;

static constexpr int CSI_MAX_IQ = 128;

typedef struct __attribute__((packed)) {
  uint8_t kind;
  int16_t rssi;
  uint16_t n_pairs;
  int8_t iq[CSI_MAX_IQ];
} csi_relay_t;

static volatile int16_t last_rssi = 0;
static volatile uint16_t last_pairs = 0;
static volatile int8_t last_iq[CSI_MAX_IQ];
static volatile bool csi_fresh = false;
static volatile uint32_t csi_total = 0;

static beacon_t beacon;
static csi_relay_t relay;
static uint32_t sent_ok = 0, relayed = 0;
static uint32_t last_report_ms = 0, sent_at_report = 0;

// Copies and returns. Nothing else belongs in a CSI callback.
static void csi_cb(void *ctx, wifi_csi_info_t *info) {
  (void)ctx;
  if (!info || !info->buf || info->len <= 0) return;
  int n = info->len;
  if (n > CSI_MAX_IQ) n = CSI_MAX_IQ;
  last_rssi = info->rx_ctrl.rssi;
  last_pairs = (uint16_t)(n / 2);
  for (int i = 0; i < n; i++) last_iq[i] = info->buf[i];
  csi_fresh = true;
  csi_total++;
}

void setup() {
  pinMode(PIN_LED, OUTPUT);
  Serial.begin(115200);
  const uint32_t t0 = millis();
  while (!Serial && (millis() - t0) < 3000) delay(50);

  Serial.println();
  Serial.println("=== TX node: beacon + remote CSI ===");

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  esp_wifi_set_ps(WIFI_PS_NONE);
  esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);

  if (esp_now_init() != ESP_OK) {
    Serial.println("FATAL: esp_now_init failed");
    while (true) delay(1000);
  }

  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, BROADCAST_MAC, 6);
  peer.channel = WIFI_CHANNEL;
  peer.encrypt = false;
  if (esp_now_add_peer(&peer) != ESP_OK) {
    Serial.println("FATAL: could not add broadcast peer");
    while (true) delay(1000);
  }

  // Force an OFDM/HT rate. Without this the broadcast goes out at a basic
  // 802.11b rate that produces no usable channel estimate at the receiver.
  esp_now_rate_config_t rate_cfg = {};
  rate_cfg.phymode = WIFI_PHY_MODE_HT20;
  rate_cfg.rate = WIFI_PHY_RATE_MCS0_LGI;
  rate_cfg.ersu = false;
  rate_cfg.dcm = false;
  const esp_err_t rate_err = esp_now_set_peer_rate_config(BROADCAST_MAC, &rate_cfg);
  Serial.printf("peer rate HT20/MCS0  -> %s\n", esp_err_to_name(rate_err));

  // Promiscuous capture, for the same reason as the bench node: without it the
  // driver drops frames before they reach the CSI stage.
  wifi_promiscuous_filter_t filt = {};
  filt.filter_mask = WIFI_PROMIS_FILTER_MASK_MGMT | WIFI_PROMIS_FILTER_MASK_DATA;
  esp_wifi_set_promiscuous_filter(&filt);
  esp_wifi_set_promiscuous(true);

  wifi_csi_config_t csi_cfg;
  memset(&csi_cfg, 0, sizeof(csi_cfg));
  // The C6 is a Wi-Fi 6 part, so wifi_csi_config_t is the acquire-config
  // bitfield layout rather than the 802.11n bool layout used on the S3.
  csi_cfg.enable = 1;
  csi_cfg.acquire_csi_legacy = 1;
  csi_cfg.acquire_csi_ht20 = 1;
  csi_cfg.acquire_csi_ht40 = 1;
  csi_cfg.acquire_csi_su = 1;
  csi_cfg.acquire_csi_mu = 1;
  csi_cfg.acquire_csi_dcm = 1;
  csi_cfg.acquire_csi_beamformed = 1;
#if defined(CONFIG_SOC_WIFI_MAC_VERSION_NUM) && CONFIG_SOC_WIFI_MAC_VERSION_NUM >= 3
  // Wi-Fi 6 MAC v3 needs LLTF forced on and an explicit STBC sampling mode,
  // otherwise every acquire flag can report success and the callback still
  // never fires - which is exactly what happened with the shorter config.
  csi_cfg.acquire_csi_force_lltf = 1;
  csi_cfg.acquire_csi_vht = 1;
  csi_cfg.acquire_csi_he_stbc_mode = ESP_CSI_ACQUIRE_STBC_SAMPLE_HELTFS;
#else
  csi_cfg.acquire_csi_he_stbc = ESP_CSI_ACQUIRE_STBC_SAMPLE_HELTFS;
#endif
  csi_cfg.dump_ack_en = 0;
  csi_cfg.val_scale_cfg = 0;
  Serial.printf("set_csi_config       -> %s\n",
                esp_err_to_name(esp_wifi_set_csi_config(&csi_cfg)));
  Serial.printf("set_csi_rx_cb        -> %s\n",
                esp_err_to_name(esp_wifi_set_csi_rx_cb(csi_cb, NULL)));
  Serial.printf("set_csi(true)        -> %s\n",
                esp_err_to_name(esp_wifi_set_csi(true)));

  Serial.printf("mac      : %s\n", WiFi.macAddress().c_str());
  Serial.printf("channel  : %u (locked)\n", WIFI_CHANNEL);
  Serial.printf("beacon   : %lu us (%.0f Hz)\n", (unsigned long)TX_INTERVAL_US,
                1000000.0 / TX_INTERVAL_US);
  Serial.printf("relay    : every %lu ms\n", (unsigned long)RELAY_INTERVAL_MS);
  Serial.println();
  Serial.println("Place several metres from the bench node, walking path between.");
  Serial.println();

  beacon.kind = MSG_BEACON;
  relay.kind = MSG_CSI;
  last_report_ms = millis();
}

void loop() {
  static uint32_t next_tx_us = 0;
  static uint32_t next_relay_ms = 0;
  const uint32_t now_us = micros();

  if ((int32_t)(now_us - next_tx_us) >= 0) {
    next_tx_us = now_us + TX_INTERVAL_US;
    beacon.seq++;
    beacon.t_us = now_us;
    if (esp_now_send(BROADCAST_MAC, (const uint8_t *)&beacon, sizeof(beacon)) == ESP_OK) {
      sent_ok++;
    }
  }

  const uint32_t now_ms = millis();
  if (csi_fresh && (int32_t)(now_ms - next_relay_ms) >= 0) {
    next_relay_ms = now_ms + RELAY_INTERVAL_MS;
    csi_fresh = false;
    relay.rssi = last_rssi;
    relay.n_pairs = last_pairs;
    const int nbytes = last_pairs * 2;
    for (int i = 0; i < nbytes && i < CSI_MAX_IQ; i++) relay.iq[i] = last_iq[i];
    // Only the bytes actually used - ESP-NOW caps a payload at 250.
    const size_t len = offsetof(csi_relay_t, iq) + (size_t)nbytes;
    if (len <= 250 && esp_now_send(BROADCAST_MAC, (const uint8_t *)&relay, len) == ESP_OK) {
      relayed++;
    }
  }

  if (now_ms - last_report_ms >= 2000) {
    const float el = (now_ms - last_report_ms) / 1000.0f;
    Serial.printf("tx %.0f Hz  csi_seen=%lu  relayed=%lu  rssi=%d\n",
                  (sent_ok - sent_at_report) / el, (unsigned long)csi_total,
                  (unsigned long)relayed, (int)last_rssi);
    last_report_ms = now_ms;
    sent_at_report = sent_ok;
    digitalWrite(PIN_LED, !digitalRead(PIN_LED));
  }
}
