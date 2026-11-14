# NodeMCU power measurements

ESP8266 firmware and recorded current measurements using STLINK-V3PWR. The recorded dataset below is an **empty-loop baseline with the built-in LED off**. It is not a blinking-LED experiment.

## Firmware

Flash one sketch at a time. The directory and `.ino` filename must match in the Arduino IDE.

| Sketch | Behavior | Expected LED behavior |
| --- | --- | --- |
| [00_no_code](00_no_code/00_no_code.ino) | Disable Wi-Fi/radio and serial interfaces, then execute an empty loop | Off; no blinking |
| [01_modem_cycle](01_modem_cycle/01_modem_cycle.ino) | Radio disabled; wait using `delay()` | On for 2 s, off for approximately 8 s |
| [02_light_cycle](02_light_cycle/02_light_cycle.ino) | Timed forced light sleep between LED tasks | On for 2 s, off for approximately 8 s |
| [03_deep_cycle](03_deep_cycle/03_deep_cycle.ino) | Deep sleep followed by restart of `setup()` | On for 2 s; sleep for approximately 8 s plus startup overhead |

The baseline contains no application task in `loop()`. The ESP8266 Arduino runtime still runs; an empty loop does not mean zero current or explicit deep sleep. All sketches explicitly use **GPIO2 / D4** for the built-in LED, verified on this board. The LED is active-low: `HIGH` turns it off. GPIO2 is configured after `Serial1.end()` because it also serves as UART1 TX. D0 / GPIO16 remains available for deep-sleep wakeup through RST.

## Hardware and software setup

| Setting | Value |
| --- | --- |
| Board notes for the recorded baseline | NodeMCU V3 |
| Arduino board selection | NodeMCU 1.0 (ESP-12E Module) |
| ESP8266 Arduino Core | 3.1.2 |
| CPU frequency | 80 MHz |
| Meter | STLINK-V3PWR, firmware V4.J7.B3.P6 |
| Supply | OUT at 3.3 V |
| Sampling frequency | 1000 Hz |

For measurement, connect **OUT → 3V3** and **GND → GND**, with NodeMCU USB disconnected. For USB flashing, disconnect the STLINK output wiring first.

Deep sleep requires **D0 → RST** for timed wakeup. If using the physical reset button, the upstream example recommends a Schottky diode with its anode at RST and cathode (stripe) at D0. Disconnect this link if it interferes with flashing.

## Methodology

### Preparation

1. Flash the selected sketch and verify its behavior.
2. Configure 3.3 V and 1000 Hz on the meter.
3. Warm up for 180 seconds with OUT enabled. The target runs during warm-up; these samples are not recorded.
4. Before each repeat, enable OUT, request manual calibration, check device status, and read meter temperature.

See the main [warm-up and calibration procedure](../README.md#warm-up-calibration-and-temperature) for settings and limitations.

### Acquisition

One run consists of **10 independent captures of 100 seconds each**. Before each capture, turn target power off for one second, then start acquisition with automatic OUT power-on. The window therefore includes **power-on startup**, followed by execution of the selected firmware.

For the baseline, the LED stays off throughout normal execution. For deep sleep, recurring startup after wakeup is part of normal operation and must remain in the energy comparison. A 100-second window does not guarantee an identical number of complete LED cycles across sketches.

Run from the repository root after flashing `00_no_code`:

```powershell
.\.venv\Scripts\python.exe stlink_measure.py capture --port COM18 --name no_code --notes "NodeMCU V3; ESP8266 Core 3.1.2; CPU 80 MHz; 00_no_code; USB disconnected" --repeats 10 --seconds 100 --hz 1000
```

### Analysis

- Calculate mean current and estimated energy separately for each 100-second capture.
- Summarize the 10 repeat results using their mean and sample standard deviation (SD).
- Calculate minimum and maximum current from all recorded samples, including startup peaks.
- Estimate energy as the sum of current samples multiplied by the configured voltage and sample interval. Voltage is a setting, not a separately sampled measurement.
- Preserve raw samples and command logs. Exclude captures with calibration/resynchronization during the analysis window rather than assuming continuous sampling.

`comparison` overlays the individual current traces. `statistics` shows one colored point per repeat and the overall mean with **±1 SD**. Repeat colors match between plots. Numerical summaries and SD appear below the plots. Reports are available in English (`_eng`) and Polish (`_pl`).

## Recorded baseline results

Dataset: [modem_20261114_202635_901512](../results/modem_20261114_202635_901512).

The original run was named `modem`, but its recorded notes say **“Zero code test”**. These results describe the supplied empty-loop baseline, not sketch `01_modem_cycle`. The original name and metadata are retained.

| Metric | Result |
| --- | --- |
| Valid captures | 10 |
| Duration per capture | 100 s |
| Mean current across captures | 20.859 mA |
| SD of mean current across captures | 0.017 mA |
| Mean estimated energy per capture | 6.884 J |
| Meter temperature before / after warm-up | 35.2°C / 35.5°C |

### Current traces

![Current traces for all ten empty-loop baseline captures](../results/modem_20261114_202635_901512/comparison_eng.png)

### Summary statistics

![Mean current and estimated energy for the empty-loop baseline](../results/modem_20261114_202635_901512/statistics_eng.png)

## Limitations and verification

Measurements include the whole powered NodeMCU board, including its regulator, USB interface circuitry, and other components powered by the selected connection. They do not isolate ESP8266 chip consumption.

The sketches have not been compiled or flashed by this repository's tooling. The baseline firmware was supplied by the experiment author. Light sleep relies on SDK timer internals: verify the low-current interval and repeated wakeups on the selected Core version before labeling results as light sleep.

Reference implementation: [ESP8266 Arduino LowPowerDemo](https://github.com/esp8266/Arduino/tree/master/libraries/esp8266/examples/LowPowerDemo).
