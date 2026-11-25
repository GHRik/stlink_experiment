"""Public Python methods exposed to the trusted desktop frontend."""
from .file_picker import FilePicker
from .serial_ports import available_ports
from .hub_discovery import available_hubs
from .hub_control import HubControl
from .capture import CaptureProcess
from .meter_power import MeterPower
from threading import Lock


class DesktopApi:
    def __init__(self, webview, settings=None):
        self._picker = FilePicker(webview)
        self._hub_control = HubControl()
        self._capture = CaptureProcess()
        self._meter_power = MeterPower()
        self._meter_lock = Lock()
        self._hub_command = (settings or {}).get("hub", {}).get("cmd", "ykushcmd")

    def _bind_window(self, window):
        self._picker._window = window

    def pick_file(self, kind):
        return self._picker.pick_file(kind)

    def list_ports(self):
        return available_ports()

    def list_hubs(self, driver):
        return available_hubs(driver, self._hub_command)

    def set_hub_port(self, driver, serial, port, enabled):
        return self._hub_control.set_port(driver, self._hub_command, serial, port, enabled)

    def start_capture(self, config):
        with self._meter_lock:
            if self._capture.status()["running"]:
                raise RuntimeError("A capture is already running")
            self._meter_power.close()
            return self._capture.start(config)

    def set_meter_power(self, port, voltage, enabled):
        with self._meter_lock:
            if self._capture.status()["running"]:
                raise RuntimeError("Manual OUT control is unavailable during capture")
            return self._meter_power.set(port, voltage, enabled)

    def capture_status(self, after=0):
        return self._capture.status(after)

    def stop_capture(self):
        self._capture.stop()

    def _on_closing(self):
        stopped = self._capture.close()
        with self._meter_lock:
            self._meter_power.close()
        return stopped
