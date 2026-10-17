# XIAO ESP32-C5 prototype bring-up

This is a USB-first OTA foundation for the XIAO ESP32-C5. It does not read the
TI radar, thermal camera, or Wi-Fi CSI yet. Keep the external 5 V lead
disconnected when flashing or powering the XIAO through USB.

Build and flash on the Mac:

```sh
pio run -d firmware/xiao-c5-bringup
pio run -d firmware/xiao-c5-bringup -t upload
pio device monitor -p /dev/cu.usbmodem1101 -b 115200
```

The serial console prints the local `Syren-C5-Setup` Wi-Fi password, the page
address, and the browser login. The password is generated on-device and kept
in NVS, not in the repository. Connect a computer or phone to that AP, open
the printed page, log in as `admin` with the same password, and upload a
future PlatformIO `firmware.bin`. The 8 MB partition table has two OTA app
slots. Keep USB available until a complete OTA update and reboot have been
tested on this particular board.

Before connecting the external 5 V rail, measure its polarity and voltage at
the intended XIAO leads. Printed labels or earlier successful use do not
verify the present soldered harness. Never power the XIAO from USB and an
unverified external rail simultaneously.
