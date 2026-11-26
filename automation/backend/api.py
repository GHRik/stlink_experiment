"""Public Python methods exposed to the trusted desktop frontend."""
from .file_picker import FilePicker
from .serial_ports import available_ports
from .hub_discovery import available_hubs
from .hub_control import HubControl
from .capture import CaptureProcess
from .meter_power import MeterPower
from .relay_control import RelayControl
from threading import Lock
import sys
import json
from .hil import hil_configuration
from .results_gallery import ResultsGallery
from .comparison import ComparisonService


class DesktopApi:
    def __init__(self, webview, settings=None):
        self._picker = FilePicker(webview)
        self._hub_control = HubControl()
        self._relay_control = RelayControl()
        self._capture = CaptureProcess()
        self._meter_power = MeterPower()
        self._meter_lock = Lock()
        self._results_gallery = ResultsGallery()
        self._comparisons = ComparisonService(webview, self._capture._directory / 'results')
        self._hub_command = (settings or {}).get("hub", {}).get("cmd", "ykushcmd")

    def _bind_window(self, window):
        self._picker._window = window

    def pick_file(self, kind):
        return self._picker.pick_file(kind)

    def list_ports(self):
        return available_ports()

    def list_results(self):
        return self._results_gallery.list_results()

    def open_result(self, relative_path):
        return self._results_gallery.open_result(relative_path)

    def result_preview(self, relative_path):
        return self._results_gallery.result_preview(relative_path)

    def compare_results(self, sessions):
        return self._comparisons.open(sessions)

    def list_hubs(self, driver):
        return available_hubs(driver, self._hub_command)

    def set_hub_port(self, driver, serial, port, enabled):
        return self._hub_control.set_port(driver, self._hub_command, serial, port, enabled)

    def set_relay(self, driver, port, channel, enabled):
        return self._relay_control.set_channel(driver, port, channel, enabled)

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

    def start_upload(self, board, port, sketch):
        with self._meter_lock:
            if self._capture.status()["running"]:
                raise RuntimeError("A capture or upload is already running")
            self._meter_power.close()
            return self._capture.start({}, command=[sys.executable, "-u", "-m",
                "automation.HIL.upload", board, port, sketch])

    def start_hil(self, config):
        with self._meter_lock:
            if self._capture.status()["running"]:
                raise RuntimeError("A capture or upload is already running")
            configuration = hil_configuration(config, self._hub_command)
            self._meter_power.close()
            return self._capture.start({}, command=[sys.executable, "-u", "-m",
                "automation.backend.hil_worker", json.dumps(configuration)])

    def confirm_connection(self, message):
        return self._picker._window.create_confirmation_dialog("One hub setup", message)

    def capture_status(self, after=0):
        return self._capture.status(after)

    def stop_capture(self):
        self._capture.stop()

    def _on_closing(self):
        stopped = self._capture.close()
        with self._meter_lock:
            self._meter_power.close()
        return stopped
