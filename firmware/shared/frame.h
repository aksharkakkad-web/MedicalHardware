/*
 * frame.h - binary wire format for the bench sensing node.
 *
 * This file is the cross-lane interface. The ESP32-S3 firmware writes this
 * format to native USB CDC; firmware/host/stream/ parses it. Both sides derive
 * from this file, so it is the only place the layout may be defined.
 *
 * Wire layout, little-endian, packed, no padding:
 *
 *   uint32 magic        0xA5A5A5A5
 *   uint8  type         1=CSI  2=THERMAL  3=RADAR
 *   uint64 t_us         esp_timer_get_time(), one shared clock for all three
 *   uint16 payload_len
 *   uint8  payload[payload_len]
 *   uint16 crc16        CRC16-CCITT over type..payload inclusive
 *
 * The header is 15 bytes and the trailer is 2, so a frame occupies
 * 17 + payload_len bytes on the wire. The CRC covers header bytes [4:15] plus
 * the payload -- that is, everything except the magic and the CRC itself.
 *
 * All three modalities timestamp off the same esp_timer_get_time(). This is
 * what makes cross-modality alignment possible, and it maps directly onto
 * device_monotonic_ms in docs/DATA_CONTRACT.md. Do not introduce a second
 * clock.
 *
 * Python equivalents for firmware/host/stream/ (struct module, '<' prefix):
 *   header   '<IBQH'   15 bytes
 *   crc      '<H'       2 bytes
 *   csi head '<hH'      4 bytes, then payload_len-4 int8 as interleaved I/Q
 *   thermal  '<768f' 3072 bytes
 *   radar    '<BBBfff' 15 bytes
 */

#ifndef SENSE_FRAME_H
#define SENSE_FRAME_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SENSE_FRAME_MAGIC 0xA5A5A5A5u

#define SENSE_FRAME_HEADER_BYTES 15u
#define SENSE_FRAME_CRC_BYTES 2u

/* Largest payload the host parser must be prepared to buffer (thermal). */
#define SENSE_FRAME_MAX_PAYLOAD 3072u

typedef enum {
  SENSE_FRAME_CSI = 1,
  SENSE_FRAME_THERMAL = 2,
  SENSE_FRAME_RADAR = 3
} sense_frame_type_t;

typedef struct __attribute__((packed)) {
  uint32_t magic;
  uint8_t type;
  uint64_t t_us;
  uint16_t payload_len;
} sense_frame_header_t;

/*
 * Type 1 - CSI.
 *
 * Payload is this header followed by 2*subcarriers interleaved int8 I/Q pairs,
 * copied verbatim out of info->buf in the CSI callback. HT20 gives 64
 * subcarriers = 128 int8 = 132 payload bytes total.
 *
 * Nothing is processed on the device: the callback copies rssi, len, buf and
 * the timestamp into a ring buffer and returns. All interpretation happens on
 * the host.
 */
typedef struct __attribute__((packed)) {
  int16_t rssi;         /* info->rx_ctrl.rssi, dBm */
  uint16_t subcarriers; /* count of I/Q pairs that follow */
} sense_csi_head_t;

/*
 * Type 2 - THERMAL.
 *
 * 32x24 row-major float32 degrees Celsius, straight from the MLX90640 driver.
 * Index [row * SENSE_THERMAL_COLS + col].
 *
 * A pixel the driver could not resolve is NaN, never 0.0. Zero is a plausible
 * temperature, so it can never double as "missing".
 */
#define SENSE_THERMAL_COLS 32u
#define SENSE_THERMAL_ROWS 24u
#define SENSE_THERMAL_PIXELS (SENSE_THERMAL_COLS * SENSE_THERMAL_ROWS)

typedef struct __attribute__((packed)) {
  float pixels[SENSE_THERMAL_PIXELS];
} sense_thermal_payload_t;

/*
 * Type 3 - RADAR.
 *
 * The MR60BHA2 does not report every field on every update, so `valid` is a
 * bitmask saying which fields this frame actually carries.
 *
 * An invalid float field MUST be transmitted as NaN and an invalid integer
 * field as its SENSE_RADAR_*_ABSENT sentinel -- never as 0. A consumer that
 * forgets to check the mask then produces obvious garbage instead of a
 * plausible lie. docs/DATA_CONTRACT.md forbids zero-filling an unavailable
 * value, and that rule starts here on the wire.
 *
 * Vital signs are only meaningful for a near-stationary subject within roughly
 * 1.5 m (heart rate) or 2 m (respiration). Outside those conditions the
 * firmware clears the bit rather than forwarding a number the sensor cannot
 * actually support.
 */
#define SENSE_RADAR_VALID_PRESENCE (1u << 0)
#define SENSE_RADAR_VALID_DISTANCE (1u << 1)
#define SENSE_RADAR_VALID_RESPIRATION (1u << 2)
#define SENSE_RADAR_VALID_HEART_RATE (1u << 3)
#define SENSE_RADAR_VALID_QUALITY (1u << 4)

#define SENSE_RADAR_PRESENCE_ABSENT 0xFFu
#define SENSE_RADAR_QUALITY_ABSENT 0xFFu

typedef struct __attribute__((packed)) {
  uint8_t valid;    /* SENSE_RADAR_VALID_* bitmask */
  uint8_t presence; /* 0, 1, or SENSE_RADAR_PRESENCE_ABSENT */
  uint8_t quality;  /* 0-100, or SENSE_RADAR_QUALITY_ABSENT */
  float distance_m;
  float respiration_rpm;
  float heart_rate_bpm;
} sense_radar_payload_t;

/*
 * CRC16-CCITT (poly 0x1021, init 0xFFFF, no input/output reflection, no final
 * XOR). Computed over the frame's header bytes [4:15] and the payload.
 */
static inline uint16_t sense_crc16(const uint8_t *data, uint32_t len) {
  uint16_t crc = 0xFFFFu;
  for (uint32_t i = 0; i < len; i++) {
    crc ^= (uint16_t)data[i] << 8;
    for (uint8_t bit = 0; bit < 8; bit++) {
      crc = (crc & 0x8000u) ? (uint16_t)((crc << 1) ^ 0x1021u) : (uint16_t)(crc << 1);
    }
  }
  return crc;
}

#ifdef __cplusplus
}
#endif

#endif /* SENSE_FRAME_H */
