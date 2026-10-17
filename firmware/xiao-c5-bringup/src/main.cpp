#include <Arduino.h>
#include <Preferences.h>
#include <Update.h>
#include <WebServer.h>
#include <WiFi.h>

// Prototype USB-first bring-up. No sensor pins or external power are used.
namespace {
constexpr char kVersion[] = "c5-bringup-1";
constexpr char kApName[] = "Syren-C5-Setup";
constexpr char kUser[] = "admin";
constexpr uint32_t kMinImageBytes = 64 * 1024;

WebServer server(80);
Preferences preferences;
String apPassword;
bool uploadFailed = false;
bool uploadFinished = false;
size_t uploadedBytes = 0;

String makePassword() {
  static constexpr char alphabet[] =
      "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
  String value;
  value.reserve(16);
  for (int i = 0; i < 16; ++i) {
    value += alphabet[esp_random() % (sizeof(alphabet) - 1)];
  }
  return value;
}

bool authorized() {
  if (server.authenticate(kUser, apPassword.c_str())) return true;
  server.requestAuthentication();
  return false;
}

void sendPage() {
  if (!authorized()) return;
  String html = "<!doctype html><html><head><meta name='viewport' "
                "content='width=device-width,initial-scale=1'><title>Syren C5</title>"
                "<style>body{font:16px system-ui;max-width:32rem;margin:3rem auto;"
                "padding:0 1rem;color:#17313a}button{padding:.7rem 1rem}"
                "</style></head><body><h1>Syren C5 setup</h1><p>Firmware: ";
  html += kVersion;
  html += "</p><p>This prototype currently provides USB serial and local OTA only. "
          "Radar, thermal, and CSI sensing are not yet implemented.</p>"
          "<form method='POST' action='/update' enctype='multipart/form-data'>"
          "<label>Choose a firmware .bin file <input type='file' name='firmware' "
          "accept='.bin' required></label><p><button type='submit'>Update firmware"
          "</button></p></form></body></html>";
  server.send(200, "text/html", html);
}

void handleUpload() {
  // Check credentials before beginning a flash write, not only in the final handler.
  if (!server.authenticate(kUser, apPassword.c_str())) {
    uploadFailed = true;
    return;
  }

  HTTPUpload &upload = server.upload();
  if (upload.status == UPLOAD_FILE_START) {
    uploadFailed = false;
    uploadFinished = false;
    uploadedBytes = 0;
    if (!upload.filename.endsWith(".bin") || !Update.begin(UPDATE_SIZE_UNKNOWN, U_FLASH)) {
      uploadFailed = true;
      Serial.println("OTA start rejected");
    }
  } else if (upload.status == UPLOAD_FILE_WRITE && !uploadFailed) {
    if (Update.write(upload.buf, upload.currentSize) != upload.currentSize) {
      uploadFailed = true;
      Update.abort();
      Serial.println("OTA write failed");
    } else {
      uploadedBytes += upload.currentSize;
    }
  } else if (upload.status == UPLOAD_FILE_END && !uploadFailed) {
    if (uploadedBytes < kMinImageBytes || !Update.end(true)) {
      uploadFailed = true;
      Update.abort();
      Serial.println("OTA image invalid or incomplete");
    } else {
      uploadFinished = true;
      Serial.printf("OTA image accepted: %u bytes\n", static_cast<unsigned>(uploadedBytes));
    }
  } else if (upload.status == UPLOAD_FILE_ABORTED) {
    uploadFailed = true;
    Update.abort();
    Serial.println("OTA upload aborted");
  }
}

void finishUpload() {
  if (!authorized()) return;
  if (uploadFailed || !uploadFinished || Update.hasError()) {
    server.send(400, "text/plain", "Update failed; previous firmware retained.");
    return;
  }
  server.send(200, "text/plain", "Update accepted. Rebooting.");
  delay(300);
  ESP.restart();
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.printf("Syren %s boot\n", kVersion);

  preferences.begin("syren-ota", false);
  apPassword = preferences.getString("ap-pass", "");
  if (apPassword.length() < 12) {
    apPassword = makePassword();
    if (preferences.putString("ap-pass", apPassword) != apPassword.length()) {
      Serial.println("Unable to save AP password; OTA AP disabled");
      return;
    }
  }
  preferences.end();

  WiFi.mode(WIFI_AP);
  if (!WiFi.softAP(kApName, apPassword.c_str())) {
    Serial.println("Unable to start OTA access point");
    return;
  }

  server.on("/", HTTP_GET, sendPage);
  server.on("/update", HTTP_POST, finishUpload, handleUpload);
  server.onNotFound([] { server.send(404, "text/plain", "Not found"); });
  server.begin();
  Serial.printf("OTA AP: %s\n", kApName);
  Serial.printf("OTA password: %s\n", apPassword.c_str());
  Serial.printf("OTA page: http://%s/ (login: %s, same password)\n",
                WiFi.softAPIP().toString().c_str(), kUser);
}

void loop() {
  server.handleClient();
  delay(2);
}
