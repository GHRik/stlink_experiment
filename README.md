# STLINK power measurements

Capture current measurements from STLINK-V3PWR, export samples to CSV, and generate plots and summary statistics. Includes a no-code baseline and three NodeMCU / ESP8266 sketches for comparing modem sleep, light sleep, and deep sleep.

## Quick start

Requires Python 3.10+, STLINK-V3PWR, and a NodeMCU board. Run these commands in PowerShell from the repository directory:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 1. Flash and connect the board

Flash one sketch from `nodemcu_led_cycles/` using the Arduino IDE. Select **NodeMCU 1.0 (ESP-12E Module)**, ESP8266 Arduino Core **3.1.2**, and **80 MHz** CPU frequency. Sketches 01–03 turn the built-in LED on for 2 seconds, then wait for approximately 8 seconds. The [00_no_code baseline](nodemcu_led_cycles/00_no_code/00_no_code.ino) disables the LED, Wi-Fi/radio, and serial interfaces, then runs an empty loop.

Disconnect STLINK output wiring while flashing over USB. For measurement, disconnect NodeMCU USB and connect **STLINK OUT → 3V3** and **GND → GND**. The script defaults to **3.3 V**. Deep sleep also requires **D0 → RST**. See the [NodeMCU documentation](nodemcu_led_cycles/README.md) for firmware behavior, methodology, and recorded results.

### 2. Find the measurement port

Release control in STM32CubeMonitor-Power and close it, along with any serial terminal using the device.

```powershell
.\.venv\Scripts\python.exe stlink_measure.py ports
```

Select the STLINK **SMU** port, rather than the debug UART port. Replace `COM18` below with your port.

### 3. Capture data

Start with a short communication check:

```powershell
.\.venv\Scripts\python.exe stlink_measure.py capture --port COM18 --name modem --notes "NodeMCU V3; ESP8266 Core 3.1.2; CPU 80 MHz; modem sketch; USB disconnected" --repeats 1 --seconds 15 --out test_results
```

Then record a series:

```powershell
.\.venv\Scripts\python.exe stlink_measure.py capture --port COM18 --name modem --notes "NodeMCU V3; ESP8266 Core 3.1.2; CPU 80 MHz; modem sketch; USB disconnected" --repeats 10 --seconds 100 --hz 1000
```

For the other sketches, flash the corresponding firmware and use `--name light` or `--name deep`. Keep voltage and sampling frequency identical across comparisons. Use `--notes "board, firmware, and measurement conditions"` to record your setup.

Both `--name` and `--notes` are required and must not be blank:

- `--name` identifies the tested configuration and names its results directory, with date and time appended automatically.
- `--notes` documents the board, firmware, and measurement conditions so results can be interpreted and reproduced. The meter cannot infer these details. Notes are saved in the session configuration and each repeat's metadata.

One invocation of `capture` is one run. `--name` is required; use a descriptive configuration name. The date and time are appended automatically. All reports belong to that run; separate invocations do not share reports. Each repeat starts by cycling the board's power.

Capture includes a warm-up phase before the series and calibration before every repeat. See [Warm-up, calibration, and temperature](#warm-up-calibration-and-temperature) for the procedure and its limitations.

```text
results/
  modem_20261114_183000_123456/
    session_config.json
    warmup.json
    repeat_001/  # samples.csv, stream.bin, metadata.json, commands.json, analysis.json, current.png/svg
    repeat_002/
    ...
    repeat_010/
    runs_summary.csv
    statistics.csv
    excluded_runs.json
    comparison_pl.png / comparison_pl.svg
    comparison_eng.png / comparison_eng.svg
    statistics_pl.png / statistics_pl.svg
    statistics_eng.png / statistics_eng.svg
```

`comparison` overlays all repeats. `statistics` shows individual repeat results and their mean ± SD, with a legend below. Both include the run directory name and are generated in Polish (`_pl`) and English (`_eng`). CSV files use a semicolon separator and a decimal point.

### 4. Analyze saved data

```powershell
.\.venv\Scripts\python.exe stlink_measure.py analyze --root results/modem_20261114_183000_123456
.\.venv\Scripts\python.exe stlink_measure.py analyze --root results/modem_20261114_183000_123456 --from-s 4 --to-s 8
```

Analysis regenerates reports and plots without changing sample CSV files. Select time windows after inspecting the traces; the tool does not detect complete LED cycles automatically. Energy is estimated from current samples and the configured voltage, and includes the whole powered board.

## Warm-up, calibration, and temperature

ST recommends leaving **OUT enabled for several minutes before measurement** to limit the effects of meter heating and automatic calibration. The firmware automatically calibrates after a change in the OUT voltage setting or a temperature shift greater than 5°C since the previous calibration. See [ST UM3291, section 2.3, tables 26–27](https://www.st.com/resource/en/user_manual/um3291-getting-started-with-stlinkv3pwr-firmware-stmicroelectronics.pdf#page=11).

The script uses **180 seconds** as a configurable starting point, not a manufacturer-specified stabilization time or a guarantee of thermal stability. Manual calibration before every repeat is this project's measurement procedure; ST does not require that cadence.

Once before each series:

1. Configure the target voltage and read fresh meter temperature.
2. Enable OUT for `--warmup-seconds` (default: 180). NodeMCU runs its flashed firmware during this phase; measurement samples are not recorded.
3. Turn OUT off and read temperature again. Save both readings in `warmup.json`.

Before each repeat:

1. Read meter temperature, enable OUT (AUX stays off), and wait one second. The target runs during calibration preparation.
2. Send `calib` with OUT enabled, allowing up to 30 seconds for acknowledgement. On tested firmware V4.J7.B3.P6, requesting calibration with OUT off returns `error calib`.
3. Drain trailing firmware messages for one second, check `status`, and read fresh temperature using `temp degc refresh`.
4. Turn OUT off and wait `--off-seconds` (default: 1), then start acquisition with automatic OUT power-on.
5. Capture the requested samples, stop acquisition, and read fresh temperature again.

Only the target's OUT supply is switched off; the STLINK remains powered over USB. The recorded window **includes target startup after power-on**, including startup current peaks, as well as subsequent deep-sleep wakeups. The target must not receive power from its own USB connection or another source.

Each repeat's `metadata.json` stores `temperature_before_calibration_C`, `temperature_before_C`, `temperature_after_C`, and the calibration acknowledgement/status. These are **meter temperatures**, not target temperatures. An acknowledgement and an `ok` status are the readiness checks used by the script; they do not independently prove thermal stability.

Override warm-up with `--warmup-seconds 300`, for example. Use `--warmup-seconds 0` to skip the delay when the setup is already warm; calibration and temperature recording still run.

Warm-up and manual calibration do not disable automatic calibration. Calibration/resynchronization inside the captured window still invalidates the repeat because this script does not reconstruct missing samples. Raw data remain available. Verify the sequence on physical hardware with a short capture before a full series.

## Run without hardware

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_stlink_measure.py
.\.venv\Scripts\python.exe stlink_measure.py demo
```

Demo output is synthetic data, saved in `demo_results/`.

New sessions under `results/`, along with `test_results/` and `demo_results/`, are ignored by Git. The baseline session documented in the [NodeMCU README](nodemcu_led_cycles/README.md#recorded-baseline-results) is explicitly included, with its raw samples and reports. Back up measurement data separately.

License: [MIT](LICENSE.txt).
