# HIL frontend prototype

## Layouts

The **HIL**, **StandAlone**, **One hub** and **One relay** tabs reposition the same device cards and retain their field values.

| Layout | Connections |
| --- | --- |
| HIL | Two hubs, STLINK, relay controller and up to three DUTs |
| StandAlone | PC → STLINK → one DUT |
| One hub | PC → STLINK → one DUT (OUT + GND); separate PC power and data connections to one hub → the same DUT over USB |
| One relay | PC → STLINK and relay controller; relay contacts → up to three DUTs |

Only visible devices reserve COM ports and hub serials. Layout switching is disabled during Run. The layout code lives in [modes.js](modes.js) and [modes.css](modes.css); device cards remain in [index.html](index.html).

## Desktop launcher

From the repository root, with the virtual environment activated:

```powershell
python -m pip install -e ".[gui]"
stlink-gui
```

For the frontend alone, use `stlink-gui --demo`. It opens sample COM ports and simulated switches without exposing the Python hardware API. **Demo mode** is shown in the header.

Both Hub 1 and Hub 2 have model and serial selectors. Demo mode provides `YK17125`, `YK21493` and `YK30001`. A serial selected for one hub is hidden from the other hub's choices. Assigned COM ports are likewise hidden from other active devices and become available again when released. Hub 1 switching remains frontend-only.

Opens the existing HTML in a separate desktop window using pywebview. **Choose file** opens a native file dialog and displays the full local path for `.ino` sketches and the optional `.py` controller. Cancel keeps the previous selection. Hub 2 supports real manual switching; Run and the other hardware switches remain simulated.

## Browser preview

Open [index.html](index.html) in a browser by double-clicking the local file. No installation or server is required. Browser file pickers expose filenames only; native full-path selection requires the desktop launcher.

Use **Light / Dark** in the page header to select a theme. The browser remembers the choice when local storage is available.

In the desktop launcher, opening a COM selector rescans serial ports and device descriptions. Choose each device explicitly; no roles are assigned automatically. Existing choices are retained, and disconnected choices are marked until reconnected or replaced. Discovery does not open serial ports. Browser preview keeps sample COM ports.

Duplicate assignments are flagged. The Run button beside the PC validates port assignments and displays a prototype message. Measurement execution and configuration persistence are not implemented.

Each DUT has a local `.ino` file picker showing the selected filename. Files stay in the browser; they are not uploaded or flashed.

Each DUT also has a board profile selector. The prototype lists the currently configured profile, `nodemcu`. **Add profile** opens [board_profiles.json](../HIL/board_profiles.json) in a new browser tab; edit the file in your editor. The static selector does not automatically reload profiles from JSON.

Select **Relay channels** (1–3) in **Relay contacts** to show the matching number of relay contacts, DUT cards and wiring branches. Only visible devices participate in port validation; selections are retained when a DUT is hidden.

**Hub 2** provides a model selector for `ykush` and `ykush3`. Opening **Hub serial number** runs `ykushcmd -l` or `ykushcmd ykush3 -l` and lists attached serial numbers. The executable defaults to `ykushcmd`; override `hub.cmd` in [backend/config.json](../backend/config.json) if needed. Discovery does not switch hub ports.

**Relay controller** provides a model selector for the supported `numato` and `lcus2` drivers. This selection is also frontend-only.

In the desktop launcher, select a **Hub 2 serial number** before switching its ports. Clicking ON/OFF calls the existing HIL Hub driver for that exact serial and physical socket, then verifies the state with `-g`. Until confirmed, the state is unknown (`?`). Model/serial changes reset displayed states. Hub controls are locked while a command is pending. No ports are switched automatically on selection or window close.

Hub 1 and all browser-preview switches remain simulated. Hub 2 shows ports for the selected DUT count.

Relay contacts use simulated clickable ON/OFF indicators for each visible channel. They are independent of real Hub 2 switching.

Active connections glow in their wiring color and show a moving dot. Inactive connections are gray. Hub 2 reflects confirmed CLI states; the remaining connections reflect simulated states.

**Run** locks all controls, including profile links and help buttons, and reveals **STOP** below it. **STOP** restores editing without resetting selections. This is a frontend run state only.

The panel above STLINK contains the existing measurement settings: sample rate, capture duration, repeats, OUT voltage, warm-up time and OUT off time. Defaults match the HIL example configuration; values remain in the browser.

The optional **Controller script** card above STLINK accepts a local `.py` file. Its connecting wire lights up when a file is selected. The help icon explains the acquisition lifecycle; the prototype does not execute the selected script.
