/*
 * M0 + M1 - toolchain proof and I2C bus scan.
 *
 * Done conditions from HARDWARE_BRINGUP_BRIEF.md:
 *   M0: the board enumerates and blinks.
 *   M1: the scan reports 0x23 or 0x5C (BH1750, proves the bus works) AND
 *       0x33 (MLX90640).
 *
 * If 0x33 is missing but the BH1750 answers, the bus itself is fine and the
 * thermal sensor's SDA/SCL are almost certainly swapped - harmless, just swap
 * them. If nothing at all answers, suspect power or the carrier seating rather
 * than the wiring order.
 *
 * Do not add pull-ups: the carrier already has them for the BH1750.
 */

#include <Arduino.h>
#include <Wire.h>

// XIAO ESP32-S3 pad D4 = GPIO5 (SDA), pad D5 = GPIO6 (SCL).
static constexpr int PIN_SDA = 5;
static constexpr int PIN_SCL = 6;

// Onboard user LED is active LOW on this board.
static constexpr int PIN_LED = LED_BUILTIN;

static constexpr uint8_t ADDR_BH1750_LOW = 0x23;
static constexpr uint8_t ADDR_BH1750_HIGH = 0x5C;
static constexpr uint8_t ADDR_MLX90640 = 0x33;

static uint32_t scan_index = 0;

void setup() {
  pinMode(PIN_LED, OUTPUT);
  Serial.begin(115200);

  // Native USB CDC enumerates after boot; give the host a moment to attach so
  // the first scan is not lost. Bounded so a headless run still proceeds.
  const uint32_t wait_start = millis();
  while (!Serial && (millis() - wait_start) < 3000) {
    delay(50);
  }

  // 400 kHz for the scan. M2 raises this to 1 MHz for 16 Hz thermal frames.
  Wire.begin(PIN_SDA, PIN_SCL, 400000);

  Serial.println();
  Serial.println("=== bench node: M0 toolchain + M1 I2C scan ===");
  Serial.printf("chip      : %s rev %d, %d core(s)\n", ESP.getChipModel(),
                ESP.getChipRevision(), ESP.getChipCores());
  Serial.printf("psram     : %u bytes\n", (unsigned)ESP.getPsramSize());
  Serial.printf("i2c pins  : SDA=GPIO%d (D4)  SCL=GPIO%d (D5) @ 400 kHz\n",
                PIN_SDA, PIN_SCL);
  Serial.println();
}

void loop() {
  // M0: a visible heartbeat, so a silent USB link is distinguishable from a
  // board that is not running at all.
  digitalWrite(PIN_LED, LOW);
  delay(60);
  digitalWrite(PIN_LED, HIGH);

  bool found_bh1750 = false;
  bool found_mlx90640 = false;
  int found_count = 0;

  Serial.printf("--- scan %lu ---\n", (unsigned long)scan_index++);

  for (uint8_t addr = 0x08; addr <= 0x77; addr++) {
    Wire.beginTransmission(addr);
    const uint8_t err = Wire.endTransmission();
    if (err != 0) {
      continue;
    }

    found_count++;
    const char *label = "unknown device";
    if (addr == ADDR_BH1750_LOW || addr == ADDR_BH1750_HIGH) {
      label = "BH1750 ambient light (on carrier)";
      found_bh1750 = true;
    } else if (addr == ADDR_MLX90640) {
      label = "MLX90640 thermal 32x24";
      found_mlx90640 = true;
    }
    Serial.printf("  0x%02X  %s\n", addr, label);
  }

  if (found_count == 0) {
    Serial.println("  (no devices responded)");
  }

  // State the M1 verdict explicitly rather than leaving it to be eyeballed.
  if (found_bh1750 && found_mlx90640) {
    Serial.println("M1 PASS: bus works and thermal sensor is present.");
  } else if (found_bh1750 && !found_mlx90640) {
    Serial.println("M1 FAIL: bus works (BH1750 answers) but 0x33 is missing.");
    Serial.println("         MLX90640 SDA/SCL are most likely swapped.");
  } else if (!found_bh1750 && found_mlx90640) {
    Serial.println("M1 PARTIAL: MLX90640 answers but the onboard BH1750 does");
    Serial.println("            not - check carrier seating before trusting M2.");
  } else {
    Serial.println("M1 FAIL: nothing on the bus. Check 3V3, ground, and that");
    Serial.println("         the XIAO is fully seated in the carrier headers.");
  }

  Serial.println();
  delay(2000);
}
