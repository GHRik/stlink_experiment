# STLINK power measurements

Measure board current with **STLINK-V3PWR** and save raw samples for analysis. Generate current traces, estimate energy, and compare repeated measurements using mean ± SD.

[![Example: NodeMCU deep-sleep current traces](results/deep_sleep_5s_flash_all_20261117_190910_277967/comparison_eng.svg)](results/deep_sleep_5s_flash_all_20261117_190910_277967/comparison_eng.svg)

## Quick Start

### 1. Install

Python 3.10+; run these commands from the repository root in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Connect

- Flash a [NodeMCU sketch](firmware/nodemcu_led_cycles/README.md), with STLINK output wiring disconnected.
- Disconnect the board's USB. Connect STLINK **OUT → 3V3** and **GND → GND**; the default supply is **3.3 V**. For timed ESP8266 deep-sleep wakeup, also connect **D0 → RST**.
- Close STM32CubeMonitor-Power and any terminal using the meter. Identify its **SMU** port:

```powershell
.\.venv\Scripts\python.exe -m src.stlink_measure ports
```

### 3. Capture and analyze

Replace `COM18` with the SMU port and match `--name` / `--notes` to your board and firmware:

```powershell
.\.venv\Scripts\python.exe -m src.stlink_measure capture --port COM18 --name no_code --notes "NodeMCU V3; Core 3.1.2; CPU 80 MHz; 00_no_code; USB disconnected" --repeats 10 --seconds 100 --hz 1000
```

Results are saved in `results/<name>_<timestamp>/`. To regenerate reports, use the directory printed after capture:

```powershell
.\.venv\Scripts\python.exe -m src.stlink_measure analyze --root results/no_code_20261114_183000_123456
```

## Detailed documentation

- [Measurement methodology and calibration](docs/methodology.md)
- [Output file formats](docs/outputs.md)
- [Interpreting the plots](docs/interpretation.md)

Firmware and results: [idle scenarios](firmware/nodemcu_nocode_cycles/README.md) · [LED cycles](firmware/nodemcu_led_cycles/README.md).

Automation: [upload and measurement sequence](automation/README.md) · [scripts running during acquisition](controllers/README.md).

## FAQ

**How can I run custom actions during a STLINK measurement?**

Use `--controller` to run a Python script alongside each capture. See the [controller README](controllers/README.md).

**How can I automate firmware uploads and switch between boards for measurement?**

See [automation](automation/README.md) for sequential firmware uploads, USB hub control, relay switching and STLINK captures.

## Citation

Record the commit used for your measurements when citing the repository.

```bibtex
@misc{panasiuk2026stlink,
  author       = {Panasiuk, Damian},
  title        = {{STLINK} Power Measurements},
  year         = {2026},
  howpublished = {GitHub repository},
  url          = {https://github.com/GHRik/stlink_experiment}
}
```

[MIT license](LICENSE.txt) · Damian Panasiuk
