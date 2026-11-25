# Automation

[Frontend prototype](frontend/README.md): open the HIL wiring diagram with sample COM port selectors in a browser.

| Directory | Purpose |
| --- | --- |
| [frontend](frontend/README.md) | HTML interface and browser preview |
| [backend](backend/README.md) | Desktop launcher, window lifecycle and native file selection |
| [HIL](HIL/README.md) | Hardware-in-the-loop using relays and a USB hub: upload firmware, switch boards and capture STLINK measurements. |
| [controllers](controllers/README.md) | Custom Python scripts running during an individual capture through `--controller`. |
