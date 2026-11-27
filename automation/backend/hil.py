"""Translate GUI fields into the existing HIL configuration format."""
from .hub_discovery import resolve_command


def hil_configuration(gui, hub_command):
    measurement = {key: float(gui[key]) for key in
                   ("seconds", "voltage", "warmup_seconds", "off_seconds")}
    measurement.update(repeats=int(gui["repeats"]), hz=int(gui["hz"]))
    if gui.get("controller"):
        measurement["controller"] = gui["controller"]
    driver = gui["relay"]["driver"]
    hub = gui["hub"]
    return {
        "hub": dict(hub, cmd=resolve_command(hub_command),
                    ports=[1] if hub["driver"] == "ykushxs" else [1, 2, 3]),
        "relay_controller": dict(gui["relay"], channels=2 if driver == "lcus2" else 4),
        "stlink": {"com": gui["port"], "measurement": measurement},
        "upload": {"arduino_cli": "arduino-cli", "timeout_s": 300},
        "timing": {"step_delay_s": 2, "port_timeout_s": 30},
        "connected_boards": [dict(board,
            name=f"{gui['name'].strip()}_{board['upload_profile']}-relay{board['relay'] + (1 if driver == 'lcus2' else 0)}",
            notes=gui["description"]) for board in gui["boards"]],
    }
