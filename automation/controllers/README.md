# Measurement controllers

Run any Python script alongside each capture:

```powershell
.\.venv\Scripts\python.exe -m src.stlink_measure capture --port COM18 --name controller_test --notes "Custom controller experiment" --repeats 1 --seconds 10 --controller automation/controllers/example.py
```

A new process starts after `ack start`, after warm-up and calibration. The sample-count limit requests shutdown before sending `stop`; errors and Ctrl+C also request shutdown. The script inherits the working directory and uses the same Python interpreter as the measurement tool. Output goes to `controller.log` in the repeat directory.

| Environment variable | Meaning |
| --- | --- |
| `STLINK_RUN_DIR` | Absolute path to the current repeat directory |
| `STLINK_DURATION_S` | Requested capture duration, seconds |
| `STLINK_START_MONOTONIC` | Host monotonic timestamp immediately before process launch |
| `STLINK_STOP_FILE` | Absolute path to the shutdown marker; exit when this file exists |

[example.py](example.py) records a timestamped event every second in `controller_events.csv`. Replace that action with your own instrument commands. Check the stop marker between actions and use timeouts for external commands. Release resources in `finally`.

Shutdown allows three seconds for cleanup, then kills an unresponsive controller. Nonzero exit or forced termination invalidates the capture. Exit code zero before capture end is allowed for finite schedules. Controllers must manage and stop any child processes they create.

Timing is synchronized to the host receiving the acquisition acknowledgement, with process startup and USB transport latency. This is not hardware-trigger synchronization.

## YKUSH XS: 5 seconds ON / 5 seconds OFF

Select [ykush_xs.py](ykush_xs.py) as the GUI controller, or add:

```powershell
--controller automation/controllers/ykush_xs.py
```

The controller discovers a single connected YKUSH XS, starts with ON, alternates every 5 seconds and disables the port on shutdown. It checks the stop marker during each wait. Confirmed switches appear in the GUI and timestamps go to the repeat's `controller.log`.

For multiple XS hubs, select one explicitly before starting the GUI or CLI:

```powershell
$env:YKUSH_XS_SERIAL = "YOUR_SERIAL"
```

`YKUSH_CMD` optionally overrides the CLI executable path. Otherwise the controller uses PATH or the standard Yepkit installation directory. Five-second holds start after each confirmed command; USB/CLI latency adds switching overhead.
