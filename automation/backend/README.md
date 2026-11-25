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

HTML, styles and JavaScript stay in [frontend](../frontend/README.md). Measurement execution stays in [HIL](../HIL/README.md); the desktop bridge does not run it yet.

Add configuration generation and process control as separate backend modules when those features are implemented. Keep the launcher limited to startup.
