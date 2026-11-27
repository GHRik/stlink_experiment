"""Manual switching through the existing HIL Hub drivers."""
from threading import Lock

from automation.backend.hubs import create_hub
from .hub_discovery import resolve_command


class HubControl:
    def __init__(self):
        self._lock = Lock()

    def set_port(self, driver, command, serial, port, enabled):
        if not isinstance(serial, str) or not serial.strip():
            raise ValueError("Select a hub serial number first")
        if driver not in ("ykush", "ykush3", "ykushxs"):
            raise ValueError("Expected ykush, ykush3 or ykushxs")
        ports = [1] if driver == "ykushxs" else [1, 2, 3]
        if type(port) is not int or port not in ports or type(enabled) is not bool:
            raise ValueError(f"Expected a port in {ports} and a boolean state")
        with self._lock:
            hub = create_hub({"driver": driver, "cmd": resolve_command(command),
                              "serial": serial.strip(), "ports": ports})
            hub.open()
            try:
                hub.set(port, enabled)
            finally:
                hub.close()
        return {"serial": serial.strip(), "port": port, "enabled": enabled,
                "readback": hub.last_status}
