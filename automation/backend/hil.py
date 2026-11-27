"""Translate GUI fields into the existing HIL configuration format."""
from .hub_discovery import resolve_command
from datetime import datetime
from pathlib import PureWindowsPath
import re


def hil_configuration(gui, hub_command):
    measurement = {key: float(gui[key]) for key in
                   ("seconds", "voltage", "warmup_seconds", "off_seconds")}
    measurement.update(repeats=int(gui["repeats"]), hz=int(gui["hz"]))
    if gui.get("controller"):
        measurement["controller"] = gui["controller"]
    driver = gui["relay"]["driver"]
    hub = gui["hub"]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    def component(value):
        return re.sub(r'[^A-Za-z0-9_-]+', '_', value).strip('_') or 'sketch'
    custom_name = gui.get('name', '').strip()
    def session_name(board, index):
        dut = board.get('dut', index + 1)
        if custom_name:
            return f"{component(custom_name)}_{timestamp}_DUT{dut}"
        return f"HIL_{timestamp}_{component(board['upload_profile'])}_{component(PureWindowsPath(board['sketch']).stem)}_DUT{dut}"
    return {
        "hub": dict(hub, cmd=resolve_command(hub_command),
                    ports=[1] if hub["driver"] == "ykushxs" else [1, 2, 3]),
        "relay_controller": dict(gui["relay"], channels=2 if driver == "lcus2" else 4),
        "stlink": {"com": gui["port"], "measurement": measurement},
        "upload": {"arduino_cli": "arduino-cli", "timeout_s": 300},
        "timing": {"step_delay_s": 2, "port_timeout_s": 30},
        "connected_boards": [dict(board,
            name=session_name(board, index),
            exact_name=True, notes=gui["description"]) for index, board in enumerate(gui["boards"])],
    }
