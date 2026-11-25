"""Public Python methods exposed to the trusted desktop frontend."""
from .file_picker import FilePicker
from .serial_ports import available_ports
from .hub_discovery import available_hubs
from .hub_control import HubControl
from .capture import CaptureProcess


class DesktopApi:
    def __init__(self, webview, settings=None):
        self._picker = FilePicker(webview)
        self._hub_control = HubControl()
        self._capture = CaptureProcess()
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
        return self._capture.start(config)

    def capture_status(self, after=0):
        return self._capture.status(after)

    def stop_capture(self):
        self._capture.stop()

    def _on_closing(self):
        return self._capture.close()
