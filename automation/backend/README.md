# Desktop backend

| Module | Responsibility |
| --- | --- |
| [launcher.py](launcher.py) | `stlink-gui` entry point, arguments and optional dependency check |
| [app.py](app.py) | Desktop window lifecycle and frontend/API wiring |
| [file_picker.py](file_picker.py) | Native file dialogs returning full local paths |

HTML, styles and JavaScript stay in [frontend](../frontend/README.md). Measurement execution stays in [HIL](../HIL/README.md); the desktop bridge does not run it yet.

Add configuration generation and process control as separate backend modules when those features are implemented. Keep the launcher limited to startup.
