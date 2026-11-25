"""Manual switching through the existing HIL Hub drivers."""
from threading import Lock

from automation.HIL.hubs import create_hub
from .hub_discovery import resolve_command


class HubControl:
    def __init__(self):
        self._lock = Lock()

    def set_port(self, driver, command, serial, port, enabled):
        if not isinstance(serial, str) or not serial.strip():
            raise ValueError("Select a hub serial number first")
        if driver not in ("ykush", "ykush3"):
            raise ValueError("Expected ykush or ykush3")
        if type(port) is not int or port not in (1, 2, 3) or type(enabled) is not bool:
            raise ValueError("Expected port 1-3 and a boolean state")
        with self._lock:
            hub = create_hub({"driver": driver, "cmd": resolve_command(command),
                              "serial": serial.strip(), "ports": [1, 2, 3]})
            hub.open()
            try:
                hub.set(port, enabled)
            finally:
                hub.close()
        return {"serial": serial.strip(), "port": port, "enabled": enabled}
