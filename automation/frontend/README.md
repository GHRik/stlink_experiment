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

**StandAlone** and **One relay** assume firmware was uploaded separately. DUT upload ports, board profiles and sketch pickers are hidden and do not participate in COM assignment.

## Desktop launcher

From the repository root, with the virtual environment activated:

```powershell
python -m pip install -e ".[gui]"
stlink-gui
```

For the frontend alone, use `stlink-gui --demo`. It opens sample COM ports and simulated switches without exposing the Python hardware API. **Demo mode** is shown in the header.

Both Hub 1 and Hub 2 have model and serial selectors. Demo mode provides `YK17125`, `YK21493` and `YK30001`. A serial selected for one hub is hidden from the other hub's choices. Assigned COM ports are likewise hidden from other active devices and become available again when released. Both hubs share the same switching handler, using the model and serial selected in the clicked card.

The selector beside each hub output or relay contact assigns its physical port/channel. Choosing an occupied channel swaps the two assignments. Available numbers follow the selected model: YKUSH XS has one port, LCUS-2 has two channels, and Numato has four. Changing an assignment resets its displayed switch state without sending hardware commands.

Opens the existing HTML in a separate desktop window using pywebview. **Choose file** opens a native file dialog and displays the full local path for `.ino` sketches and the optional `.py` controller. Cancel keeps the previous selection. All four Run layouts and the manual STLINK, hub and relay controls use the backend.

### One hub Run

1. Disable the assigned DUT USB port and check STLINK with OUT ON/OFF.
2. Confirm that STLINK has been disconnected from the PC.
3. Enable the DUT USB port and compile/upload the selected sketch with its board profile and COM port. Arduino CLI output appears in the log.
4. Disable the DUT USB port and ask you to reconnect STLINK.
5. Check STLINK with OUT ON/OFF, retrying up to three times with 5-second intervals.
6. Start the same capture as StandAlone, including the optional controller.

Cancel or a failed step stops the sequence before measurement. STOP during upload waits for the uploader to finish, disables the DUT USB port and skips capture.

### One relay Run

Disable all physical relay channels (four for Numato, two for LCUS-2), then disable STLINK OUT. For each visible DUT in order: enable its mapped relay channel, wait 2 seconds, run the StandAlone capture, disable that channel and wait 2 seconds. Each capture uses the test name with `_relayN` appended, where N is the physical channel number shown in the GUI. Measurement settings and the optional controller are shared across captures. STOP waits for capture cleanup before disabling the active relay; subsequent DUTs are skipped.

### HIL Run

Generate a configuration from the GUI and launch the existing [HIL runner](../HIL/run.py). Each `connected_boards` entry uses the selected profile, sketch, upload COM, physical Hub 2 socket and relay channel. Names follow `<test_name>_<board_profile>-relayN`, with one-based physical channel N. Description becomes measurement notes; the optional controller is passed to capture.

The runner manages the DUT hub (Hub 2), relays, uploads and measurements. Hub 1 remains under manual control and must keep the STLINK, relay controller and Hub 2 connected. Logs appear in the GUI; the runner saves its configuration and results under `results/automation_...`. STOP delegates interruption and cleanup to `run.py`.

The PC card's **Connect via USB HUB** switch is enabled by default in HIL. Disable it to hide the upstream hub and its external supply. STLINK, the relay controller and Hub 2 then connect directly to PC with separate USB lines. Hidden Hub 1 no longer reserves its serial number or gates connection animations. The DUT hub and HIL configuration remain the same.

## Run progress

During a desktop Run, confirmed STLINK OUT, hub-port and relay-channel events update the diagram while controls stay locked. The **Run progress** panel tracks uploads, warm-up, calibrations, completed repeats and reports across DUTs. Remaining programmed time covers warm-up and acquisition only; compilation, calibration, switching, analysis and reports add variable overhead. STOP preserves the completed counters.

The remaining-time counter is displayed prominently. CLI output stays collapsed under **Show more**; this read-only log can be expanded during a Run.

## Live current

The local canvas shows the last 30 seconds of the active acquisition, resetting for each repeat and DUT. The mean line and minimum–maximum envelope use approximately 50 ms bins (one sample per bin at low rates), delivered about every 0.5 seconds. Full-resolution samples and report statistics are unaffected. The final trace stays visible after completion or STOP.

**Demo preview** generates explicitly labelled simulated data without hardware or internet access. Starting a real Run stops the demo automatically. During warm-up and calibration the plot waits for acquisition; those stages do not collect current samples.

## Results gallery

The **Results** gallery at the bottom loads all English comparison/statistics plots under `results/`, including nested HIL sessions, sorted by session date descending (file modification time is used only for undated sessions). Each result set is collapsed by default; click its name to show the previews. **Search results** filters session names and dates as you type. The gallery refreshes after a Run finishes. Click either preview to open its full SVG in the system browser (PNG when SVG is unavailable). Existing measurements are included without regeneration.

## Browser preview

Open [index.html](index.html) in a browser by double-clicking the local file. No installation or server is required. Browser file pickers expose filenames only; native full-path selection requires the desktop launcher.

Use **Light / Dark** in the page header to select a theme. The browser remembers the choice when local storage is available.

In the desktop launcher, opening a COM selector rescans serial ports and device descriptions. Choose each device explicitly; no roles are assigned automatically. Existing choices are retained, and disconnected choices are marked until reconnected or replaced. Discovery does not open serial ports. Browser preview keeps sample COM ports.

Duplicate assignments are flagged. In StandAlone, Run passes the SMU port, test name, description, repeats, capture time and sampling rate to the existing capture CLI. Notes are taken directly from Description. Voltage, warm-up, OUT off time and an optional controller are passed too. CLI diagnostics stream into the measurement log; results use the repository's `results/` directory. STOP requests normal capture cleanup. Closing the window also requests STOP and waits for cleanup.

The STLINK **OUT ON/OFF** button uses the selected SMU port. ON applies **OUT voltage [V]** and enables VOUT; OFF disables power and releases the connection. Acknowledgement updates the displayed state. Capture takes over the meter connection and retains its normal warm-up, calibration and power-cycle sequence. Manual OUT commands are blocked during capture. Window close also disables manually enabled OUT.

Each DUT has a local `.ino` file picker showing the selected filename. Files stay in the browser; they are not uploaded or flashed.

Each DUT also has a board profile selector. The prototype lists the currently configured profile, `nodemcu`. **Add profile** opens [board_profiles.json](../HIL/board_profiles.json) in a new browser tab; edit the file in your editor. The static selector does not automatically reload profiles from JSON.

Select **Relay channels** (1–3) in **Relay contacts** to show the matching number of relay contacts, DUT cards and wiring branches. Only visible devices participate in port validation; selections are retained when a DUT is hidden.

**Hub 2** provides a model selector for `ykush` and `ykush3`. Opening **Hub serial number** runs `ykushcmd -l` or `ykushcmd ykush3 -l` and lists attached serial numbers. The executable defaults to `ykushcmd`; override `hub.cmd` in [backend/config.json](../backend/config.json) if needed. Discovery does not switch hub ports.

**Relay controller** selects the existing `numato` or `lcus2` driver and COM port. Each ON/OFF button switches its corresponding physical channel through that driver. No COM selection means the buttons are disabled. Numato confirms state readback; LCUS-2 reports command write/flush completion. Changing COM or model resets the displayed states to unknown (`?`); it does not switch hardware.

LCUS-2 supports at most two relay channels. Selecting it limits the channel selector and the HIL / One relay DUT count to two (or fewer if the selected DUT hub has only one port).

**One hub** and **HIL Hub 2** also support **YKUSH XS** (`ykushxs`), showing only port 1 and one DUT. HIL Hub 1 requires three downstream sockets, so XS is unavailable there. Switching to HIL clears an incompatible Hub 1 XS selection. Discovery uses `ykushcmd ykushxs -l`; switching and readback use `-u`, `-d` and `-g` without a trailing port number.

In the desktop launcher, select a **hub model and serial number** before switching its ports. Clicking ON/OFF calls the existing HIL Hub driver for that exact serial and physical socket, then verifies the state with `-g`. Until confirmed, the state is unknown (`?`). Model/serial changes reset displayed states. Hub controls are locked while a command is pending. No ports are switched automatically on selection or window close.

All browser-preview switches remain simulated. Hub 2 shows ports for the selected DUT count.

Relay contacts show ON/OFF after the driver completes the command. Model-specific errors are shown unchanged. The COM connection is closed after each manual operation without resetting other channels.

Active connections glow in their wiring color and show a moving dot. Inactive connections are gray. Desktop manual controls reflect completed backend commands; demo mode remains simulated.

**Run** locks all controls, including profile links and help buttons, and reveals **STOP** below it. Editing is restored when capture finishes or stops, without resetting selections. In demo and other layouts, Run/STOP only simulate this state.

The panel above STLINK contains the existing measurement settings: sample rate, capture duration, repeats, OUT voltage, warm-up time and OUT off time. Defaults match the HIL example configuration; values remain in the browser.

The optional **Controller script** card above STLINK accepts a local `.py` file. Its connecting wire lights up when a file is selected. The help icon explains the acquisition lifecycle; the prototype does not execute the selected script.
