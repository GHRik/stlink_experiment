# Measurement methodology and calibration

[Quick Start](../README.md#quick-start) · [Output files](outputs.md) · [Plot interpretation](interpretation.md)

## Test platform

| Component | Requirement |
| --- | --- |
| Host | Python 3.10+; commands below use Windows PowerShell |
| Meter | STLINK-V3PWR, SMU COM port |
| Current target | NodeMCU / ESP8266; Arduino Core 3.1.2; CPU 80 MHz |
| Arduino board selection | NodeMCU 1.0 (ESP-12E Module) |

## Capture settings

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
| `--controller` | Optional Python script running during each capture; [example and interface](../controllers/README.md) |

Change `--name` and `--notes` to match the flashed sketch. Keep voltage and sampling frequency identical across comparisons.

Optional actions during acquisition: [measurement controllers](../controllers/README.md). Sequential upload and board selection: [automation](../automation/README.md).

## Warm-up, calibration, and temperature

**180 s warm-up → calibration with OUT enabled → target power-off → capture from power-on.** Meter temperature is recorded before calibration, before capture, and after capture. Measurements include startup peaks.


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
