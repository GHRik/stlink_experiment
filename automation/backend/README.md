# Desktop backend

| Module | Responsibility |
| --- | --- |
| [launcher.py](launcher.py) | `stlink-gui` entry point, arguments and optional dependency check |
| [app.py](app.py) | Desktop window lifecycle and frontend/API wiring |
| [api.py](api.py) | Public bridge methods delegating to backend services |
| [file_picker.py](file_picker.py) | Native file dialogs returning full local paths |
| [config.json](config.json) / [config.py](config.py) | Desktop defaults; `hub.cmd` selects the CLI executable, default `ykushcmd` |
| [serial_ports.py](serial_ports.py) | Serial device enumeration through pyserial; no ports are opened |
| [hub_discovery.py](hub_discovery.py) | YKUSH serial discovery through the selected model subcommand, e.g. `ykushcmd ykush -l` |
| [hub_control.py](hub_control.py) | Manual switching of the selected hub through existing HIL Hub drivers and state readback |
| [relay_control.py](relay_control.py) | Manual switching through existing Numato and LCUS-2 drivers; closes COM after each command |
| [capture.py](capture.py) | StandAlone CLI argument mapping, capture subprocess, log stream and STOP request |
| [capture_worker.py](capture_worker.py) | Existing capture CLI with a cooperative STOP watcher; measurement cleanup remains in the capture script |
| [hil.py](hil.py) / [hil_worker.py](hil_worker.py) | GUI configuration mapping and execution through the existing HIL runner |
| [results_gallery.py](results_gallery.py) | English summary-plot discovery, lazy previews and opening full-size plots |
| [meter_power.py](meter_power.py) | Manual OUT commands through the existing Device protocol; keeps the connection while powered and releases it before capture |

HTML, styles and JavaScript stay in [frontend](../frontend/README.md). StandAlone Run invokes the existing measurement CLI; HIL Run generates a configuration for the existing [HIL runner](../HIL/README.md).

`capture.py` creates a temporary JSONL telemetry file and passes its path as `STLINK_GUI_EVENT_FILE`. The runner and its child processes append confirmed hardware changes and measurement progress through [events.py](../../src/events.py). Status polling returns new events with the same cursor as log lines, even when a child writes its stdout to a separate log. Final events are collected before temporary-file cleanup. Outside the GUI, telemetry is disabled unless the environment variable is set.

[live_current.py](../../src/live_current.py) aggregates preview samples into approximately 50 ms bins. The `current_samples` event includes the capture name and repeat number; its points are `[time_s, mean_mA, min_mA, max_mA]`. Batches use the same telemetry channel in all layouts, including HIL child captures. Aggregation is disabled for ordinary CLI runs without GUI telemetry.
