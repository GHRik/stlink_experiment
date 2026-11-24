# STLINK power measurements

Measure board current with **STLINK-V3PWR**. Save raw samples, generate current traces, and compare repeat results with mean ± SD.

[NodeMCU firmware & results](nodemcu_led_cycles/README.md) · [Quick start](#quick-start) · [Measurement procedure](#warm-up-calibration-and-temperature) · [Citation](#citation)

## Requirements

| Component | Requirement |
| --- | --- |
| Host | Python 3.10+; commands below use Windows PowerShell |
| Meter | STLINK-V3PWR, SMU COM port |
| Current target | NodeMCU / ESP8266; Arduino Core 3.1.2; CPU 80 MHz |
| Arduino board selection | NodeMCU 1.0 (ESP-12E Module) |

## Quick start

### 1. Install dependencies

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Flash and connect

- Flash one [NodeMCU sketch](nodemcu_led_cycles/README.md); disconnect STLINK output wiring while flashing over USB.
- For measurement, disconnect NodeMCU USB. Connect **OUT → 3V3**, **GND → GND**. Default supply: **3.3 V**.
- For deep sleep, also connect **D0 → RST**. All sketches use **GPIO2 / D4** for the LED.
- Release control in STM32CubeMonitor-Power and close it and any serial terminal using the meter.

### 3. Find the SMU port

```powershell
.\.venv\Scripts\python.exe stlink_measure.py ports
```

Use the **SMU port**, not the debug UART. Replace `COM18` below.

### 4. Capture

After flashing `00_no_code`, run a short check:

```powershell
.\.venv\Scripts\python.exe stlink_measure.py capture --port COM18 --name no_code --notes "NodeMCU V3; Core 3.1.2; CPU 80 MHz; 00_no_code; USB disconnected" --repeats 1 --seconds 15 --out test_results
```

Then capture the full series:

```powershell
.\.venv\Scripts\python.exe stlink_measure.py capture --port COM18 --name no_code --notes "NodeMCU V3; Core 3.1.2; CPU 80 MHz; 00_no_code; USB disconnected" --repeats 10 --seconds 100 --hz 1000
```

| Option | Why / default |
| --- | --- |
| `--name` | **Required.** Identifies the configuration and names its results directory; date/time are appended. |
| `--notes` | **Required.** Records board, firmware, and conditions needed to interpret and reproduce the measurement. |
| `--repeats` | 10 independent captures |
| `--seconds` | 100 seconds per capture |
| `--hz` | 1000 samples/second |
| `--voltage` | 3.3 V |
| `--warmup-seconds` | 180 seconds with OUT enabled before the series; `0` skips the delay |
| `--off-seconds` | 1 second with target power off before acquisition |
| `--controller` | Optional Python script running during each capture; [example and interface](controllers/README.md) |

Standalone upload: `python upload.py nodemcu COM22 path/to/sketch.ino`. Board profiles are defined in [board_profiles.json](board_profiles.json); compiler and uploader diagnostics come directly from Arduino CLI.

Change `--name` and `--notes` to match the flashed sketch. Keep voltage and sampling frequency identical across comparisons.

### 5. Recreate reports

Replace the example directory with your run directory:

```powershell
.\.venv\Scripts\python.exe stlink_measure.py analyze --root results/no_code_20261114_183000_123456
```

Optional analysis window: append `--from-s 4 --to-s 8`. Reports and plots are regenerated; raw sample CSV files are preserved.

## Outputs

**One command = one run directory:** `results/<name>_<date>_<time>/`.

| Location / file | Contents |
| --- | --- |
| `repeat_001/` … `repeat_010/` | Raw `samples.csv`, received `stream.bin`, metadata, command log, analysis, and individual current plot |
| `comparison_pl.*`, `comparison_eng.*` | All repeat traces, with matching repeat colors |
| `statistics_pl.*`, `statistics_eng.*` | Individual repeat results, mean ± SD, and numerical summaries |
| `runs_summary.csv`, `statistics.csv` | Per-repeat and aggregate results |
| `session_config.json`, `warmup.json` | Setup and warm-up temperatures |
| `excluded_runs.json` | Excluded measurements and reasons |

Plots are saved as PNG and SVG. CSV uses semicolons and decimal points. New result directories are ignored by Git; the documented [baseline dataset](nodemcu_led_cycles/README.md) is explicitly included. Back up raw measurements separately.

## Warm-up, calibration, and temperature

**180 s warm-up → calibration with OUT enabled → target power-off → capture from power-on.** Meter temperature is recorded before calibration, before capture, and after capture. Measurements include startup peaks.

<details>
<summary>Procedure, ST recommendations, and limitations</summary>

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

</details>

## Interpretation

- Measurements cover the **whole powered board**, not just the microcontroller.
- Energy is estimated from current samples and configured voltage; voltage is not separately sampled.
- ±SD describes variation **between repeat results**, not the minimum-to-maximum range.
- Current traces use up to 2500 time bins: the line shows each bin's mean and the shaded band its minimum–maximum range. Calculations use all samples. The band is not SD or measurement uncertainty. SVG plots can be enlarged without losing sharpness; individual raw samples remain in CSV files.
- Current and comparison plots show the trace from 0.2 s onward on the left and power-on startup (0–0.2 s) on the right, using raw samples. Both panels use their own axis scales; summary statistics still cover the full selected analysis window, including startup when selected.
- Individual current plots mark each panel's raw minimum in blue and maximum in orange. Comparison plots list each repeat's raw range below the panels and highlight the series extrema there, including tied results; the traces have no extrema annotations.
- Statistics plots list each repeat's mean current and total estimated energy below their respective panels. Blue and orange highlights identify the smallest and largest repeat results, not individual sample extremes. Coloured repeat keys appear in these lists without a duplicate legend.
- Complete task cycles are not detected automatically. Fixed-duration windows can contain different numbers of cycles.
- Calibration/resynchronization during acquisition invalidates the repeat; raw data are retained.

## Without hardware

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_stlink_measure.py
.\.venv\Scripts\python.exe stlink_measure.py demo
```

Demo creates **synthetic data** in `demo_results/`.

## License

[MIT](LICENSE.txt) · Damian Panasiuk

## Citation

Copy this BibTeX entry to cite the repository. For reproducibility, also record the commit used for your measurements.

```bibtex
@misc{panasiuk2026stlink,
  author       = {Panasiuk, Damian},
  title        = {{STLINK} Power Measurements},
  year         = {2026},
  howpublished = {GitHub repository},
  url          = {https://github.com/GHRik/stlink_experiment}
}
```
