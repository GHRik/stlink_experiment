# NodeMCU empty-loop measurements

Five independent sketches to compare initialization choices with an empty `loop()`. Flash one at a time using **NodeMCU 1.0 (ESP-12E Module)**, ESP8266 Arduino Core **3.1.2**, and **80 MHz**. See the main [quick start](../README.md) for measurement instructions.

These variants are independent, not cumulative. Unmentioned peripherals and GPIOs are left at their runtime defaults. Only scenario 05 explicitly turns off the GPIO2 LED.

## 01 — Empty

[Sketch](01_empty/01_empty.ino): empty `setup()` and empty `loop()`. The Arduino runtime still executes; this is not CPU sleep.

**Results: Ongoing.**

## 02 — Wi-Fi off

[Sketch](02_wifi_off/02_wifi_off.ino): disable Wi-Fi with `WiFi.mode(WIFI_OFF)` and disable persistent configuration writes. No explicit forced modem sleep or UART changes.

**Results: Ongoing.**

## 03 — Serial off

[Sketch](03_serial_off/03_serial_off.ino): call `Serial.end()` and `Serial1.end()` for ESP8266's two hardware UART interfaces. No explicit Wi-Fi, radio, or LED changes; boot-ROM serial output occurs before `setup()` and is unaffected.

**Results: Ongoing.**

## 04 — Radio off

[Sketch](04_radio_off/04_radio_off.ino): request forced modem sleep with `WiFi.forceSleepBegin()`. This also switches Wi-Fi to `WIFI_OFF` internally, so it does not isolate radio shutdown from Wi-Fi shutdown; it isolates this API call from the UART and LED changes.

Reference: [ESP8266 Arduino Core 3.1.2 implementation](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266WiFi/src/ESP8266WiFiGeneric.cpp#L485).

**Results: Ongoing.**

## 05 — All off

[Sketch](05_all_off/05_all_off.ino): the supplied baseline initialization — disable Wi-Fi, request modem sleep, end both UART interfaces, and turn off the GPIO2 / D4 LED after releasing UART1. This does not disable every chip peripheral or enter CPU deep sleep.

**Results: Ongoing.**

## Recording

Use a distinct `--name` for each sketch, such as `nocode_empty`, `nocode_wifi_off`, `nocode_serial_off`, `nocode_radio_off`, and `nocode_all_off`. Record the actual sketch, board, Core version, clock, and wiring in `--notes`. Keep all other measurement conditions identical.

No compilation, flashing, or hardware measurements have been performed for these new sketches.
