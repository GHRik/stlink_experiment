# HIL frontend prototype

Open [index.html](index.html) in a browser by double-clicking the local file. No installation or server is required.

The wiring diagram provides sample COM port selectors for STLINK, the relay controller and three DUTs. Duplicate assignments are flagged. The Run button beside the PC validates port assignments and displays a prototype message. Hardware access and configuration persistence are not implemented.

Each DUT has a local `.ino` file picker showing the selected filename. Files stay in the browser; they are not uploaded or flashed.

Each DUT also has a board profile selector. The prototype lists the currently configured profile, `nodemcu`. **Add profile** opens [board_profiles.json](../HIL/board_profiles.json) in a new browser tab; edit the file in your editor. The static selector does not automatically reload profiles from JSON.

Select **Relay channels** (1–3) in **Relay contacts** to show the matching number of relay contacts, DUT cards and wiring branches. Only visible devices participate in port validation; selections are retained when a DUT is hidden.

**Hub 2** provides a model selector for the supported `ykush` and `ykush3` drivers. The selection is local to the prototype and does not query hardware.

**Relay controller** provides a model selector for the supported `numato` and `lcus2` drivers. This selection is also frontend-only.

Both hubs show output-port LEDs with ON/OFF labels. Click a port row to toggle its simulated state. Hub 2 shows ports for the selected DUT count; these indicators do not read or control hardware.

Relay contacts use the same clickable ON/OFF indicators for each visible channel. Hub and relay switches are independent in this prototype.
