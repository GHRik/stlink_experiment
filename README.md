# STLINK power measurements

Capture current measurements from STLINK-V3PWR, export samples to CSV, and generate plots and summary statistics. Includes three NodeMCU / ESP8266 sketches for comparing modem sleep, light sleep, and deep sleep.

## Quick start

Requires Python 3.10+, STLINK-V3PWR, and a NodeMCU board. Run these commands in PowerShell from the repository directory:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 1. Flash and connect the board

Flash one sketch from `nodemcu_led_cycles/` using the Arduino IDE. Select **NodeMCU 1.0 (ESP-12E Module)**, ESP8266 Arduino Core **3.1.2**, and **80 MHz** CPU frequency. Each sketch turns the built-in LED on for 2 seconds, then waits for approximately 8 seconds.

Disconnect STLINK output wiring while flashing over USB. For measurement, disconnect NodeMCU USB and connect **STLINK OUT → 3V3** and **GND → GND**. The script defaults to **3.3 V**. Deep sleep also requires **D0 → RST**. See [sketch notes](nodemcu_led_cycles/README.txt) for details.

### 2. Find the measurement port

Release control in STM32CubeMonitor-Power and close it, along with any serial terminal using the device.

```powershell
.\.venv\Scripts\python.exe stlink_measure.py ports
```

Select the STLINK **SMU** port, rather than the debug UART port. Replace `COM18` below with your port.

### 3. Capture data

Start with a short communication check:

```powershell
.\.venv\Scripts\python.exe stlink_measure.py capture --port COM18 --name modem --repeats 1 --seconds 15 --out test_results
```

Then record a series:

```powershell
.\.venv\Scripts\python.exe stlink_measure.py capture --port COM18 --name modem --repeats 10 --seconds 120 --hz 1000
```

For the other sketches, flash the corresponding firmware and use `--name light` or `--name deep`. Keep voltage and sampling frequency identical across comparisons. Use `--notes "board, firmware, and measurement conditions"` to record your setup.

Each repeat starts by cycling the board's power. Results are saved under a timestamped session in `results/`, including raw samples (`samples.csv`), the received stream (`stream.bin`), metadata, command logs, and PNG/SVG plots. CSV files use a semicolon separator and a decimal point.

### 4. Analyze saved data

```powershell
.\.venv\Scripts\python.exe stlink_measure.py analyze --root results
.\.venv\Scripts\python.exe stlink_measure.py analyze --root results --from-s 4 --to-s 8
```

Analysis regenerates reports and plots without changing sample CSV files. Select time windows after inspecting the traces; the tool does not detect complete LED cycles automatically. Energy is estimated from current samples and the configured voltage, and includes the whole powered board.

## Run without hardware

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_stlink_measure.py
.\.venv\Scripts\python.exe stlink_measure.py demo
```

Demo output is synthetic data, saved in `demo_results/`.

`results/`, `test_results/`, and `demo_results/` are ignored by Git. Back up measurement data separately.

License: [MIT](LICENSE.txt).
