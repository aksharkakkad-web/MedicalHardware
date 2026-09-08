/*
 * M4 TX - ESP-NOW beacon.
 *
 * Broadcasts a small fixed payload on a timer so the bench node's CSI callback
 * has something to measure. Target is 2 ms between packets (500 Hz), which the
 * brief derives from gait Doppler at 5.32 GHz; typical hobby setups run 10-20 Hz
 * and produce unusable data.
 *
 * ESP-NOW rather than an AP association: it is connectionless, needs no router,
 * and gives direct control over packet timing.
 *
 * The channel is locked explicitly here and must match the RX node exactly.
 * Nothing works if these disagree, and the failure is silent.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

// Must match the RX node. Change both or neither.
static constexpr uint8_t WIFI_CHANNEL = 6;

// 2 ms between packets = 500 packets/sec.
static constexpr uint32_t TX_INTERVAL_US = 2000;

static constexpr int PIN_LED = LED_BUILTIN;

static uint8_t BROADCAST_MAC[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

// Small and fixed. The CSI estimate comes from the packet's preamble, so the
// payload only needs to be big enough to carry a sequence number for loss
// accounting.
typedef struct __attribute__((packed)) {
  uint32_t seq;
  uint32_t t_us;
} beacon_t;

static beacon_t beacon;
static uint32_t sent_ok = 0;
static uint32_t send_failed = 0;
static uint32_t cb_ok = 0;
static uint32_t cb_fail = 0;
static uint32_t last_report_ms = 0;
static uint32_t sent_at_last_report = 0;

static void on_sent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  (void)info;
  if (status == ESP_NOW_SEND_SUCCESS) {
    cb_ok++;
  } else {
    cb_fail++;
  }
}

void setup() {
  pinMode(PIN_LED, OUTPUT);
  Serial.begin(115200);
  const uint32_t t0 = millis();
  while (!Serial && (millis() - t0) < 3000) delay(50);

  Serial.println();
  Serial.println("=== TX node: M4 ESP-NOW beacon ===");

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  // Power save will happily insert sleep gaps into a 500 Hz stream.
  esp_wifi_set_ps(WIFI_PS_NONE);

  if (esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE) != ESP_OK) {
    Serial.println("FATAL: could not lock the Wi-Fi channel.");
    while (true) delay(1000);
  }

  if (esp_now_init() != ESP_OK) {
    Serial.println("FATAL: esp_now_init failed.");
    while (true) delay(1000);
  }
  esp_now_register_send_cb(on_sent);

  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, BROADCAST_MAC, 6);
  peer.channel = WIFI_CHANNEL;
  peer.encrypt = false;
  if (esp_now_add_peer(&peer) != ESP_OK) {
    Serial.println("FATAL: could not add the broadcast peer.");
    while (true) delay(1000);
  }

  Serial.printf("mac      : %s\n", WiFi.macAddress().c_str());
  Serial.printf("channel  : %u (locked)\n", WIFI_CHANNEL);
  Serial.printf("interval : %lu us  (target %.0f Hz)\n",
                (unsigned long)TX_INTERVAL_US, 1000000.0 / TX_INTERVAL_US);
  Serial.println();
  Serial.println("Place this node several metres from the bench node, with the");
  Serial.println("walking path between them. Do not put it on the bench.");
  Serial.println();

  last_report_ms = millis();
}

void loop() {
  static uint32_t next_tx_us = 0;
  const uint32_t now_us = micros();

  // Paced on the microsecond clock rather than delay(), which cannot resolve
  // 2 ms reliably once the radio starts competing for time.
  if ((int32_t)(now_us - next_tx_us) >= 0) {
    next_tx_us = now_us + TX_INTERVAL_US;

    beacon.seq++;
    beacon.t_us = now_us;
    if (esp_now_send(BROADCAST_MAC, (const uint8_t *)&beacon, sizeof(beacon)) ==
        ESP_OK) {
      sent_ok++;
    } else {
      send_failed++;
    }
  }

  const uint32_t now_ms = millis();
  if (now_ms - last_report_ms >= 2000) {
    const float elapsed = (now_ms - last_report_ms) / 1000.0f;
    const float rate = (sent_ok - sent_at_last_report) / elapsed;
    last_report_ms = now_ms;
    sent_at_last_report = sent_ok;

    digitalWrite(PIN_LED, !digitalRead(PIN_LED));

    // The achieved rate is what matters downstream, so print it rather than
    // the configured target.
    Serial.printf("tx %.0f Hz  sent=%lu queue_fail=%lu  acked=%lu nack=%lu\n",
                  rate, (unsigned long)sent_ok, (unsigned long)send_failed,
                  (unsigned long)cb_ok, (unsigned long)cb_fail);
  }
}
