# Desktop backend

| Module | Responsibility |
| --- | --- |
| [launcher.py](launcher.py) | `stlink-gui` entry point, arguments and optional dependency check |
| [app.py](app.py) | Desktop window lifecycle and frontend/API wiring |
| [api.py](api.py) | Public bridge methods delegating to backend services |
| [file_picker.py](file_picker.py) | Native file dialogs returning full local paths |
| [config.json](config.json) / [config.py](config.py) | Desktop defaults; `hub.cmd` selects the CLI executable, default `ykushcmd` |
| [serial_ports.py](serial_ports.py) | Serial device enumeration through pyserial; no ports are opened |
| [hub_discovery.py](hub_discovery.py) | YKUSH serial discovery through `ykushcmd -l` or `ykushcmd ykush3 -l` |
| [hub_control.py](hub_control.py) | Manual switching of the selected hub through existing HIL Hub drivers and state readback |
| [relay_control.py](relay_control.py) | Manual switching through existing Numato and LCUS-2 drivers; closes COM after each command |
| [capture.py](capture.py) | StandAlone CLI argument mapping, capture subprocess, log stream and STOP request |
| [capture_worker.py](capture_worker.py) | Existing capture CLI with a cooperative STOP watcher; measurement cleanup remains in the capture script |
| [meter_power.py](meter_power.py) | Manual OUT commands through the existing Device protocol; keeps the connection while powered and releases it before capture |

HTML, styles and JavaScript stay in [frontend](../frontend/README.md). StandAlone Run invokes the existing measurement CLI. Batch execution stays in [HIL](../HIL/README.md) and is not connected to GUI Run yet.

Add configuration generation and process control as separate backend modules when those features are implemented. Keep the launcher limited to startup.
