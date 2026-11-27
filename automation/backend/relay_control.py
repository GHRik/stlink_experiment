"""Manual relay switching delegated to the existing HIL drivers."""
from threading import Lock

from automation.backend.relays import create_relay


class RelayControl:
    def __init__(self):
        self._lock = Lock()

    def set_channel(self, driver, port, channel, enabled):
        with self._lock:
            relay = create_relay({"driver": driver, "port": port,
                                  "channels": 2 if driver == "lcus2" else 4})
            try:
                relay.open()
                relay.set(channel, enabled)
            finally:
                relay.close()
        return {"channel": channel, "enabled": enabled,
                "confirmation": "readback" if driver == "numato" else "write_and_flush"}
