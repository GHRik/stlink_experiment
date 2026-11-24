import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from automation import run


class FakeHardware:
    def __init__(self, fail=None):
        self.events = []
        self.relays = {i: True for i in range(4)}
        self.ports = {i: True for i in range(1, 4)}
        self.fail = fail

    def open(self):
        self.events.append(("open",))

    def relay(self, channel, enabled):
        if enabled:
            assert not any(self.relays.values())
            assert not any(self.ports.values())
        self.relays[channel] = enabled
        self.events.append(("relay", channel, enabled))

    def usb(self, port, enabled):
        assert not any(self.relays.values())
        self.ports[port] = enabled
        self.events.append(("usb", port, enabled))

    def pause(self):
        pass

    def wait_port(self, port):
        self.events.append(("wait_port", port))

    def flash(self, board):
        assert not any(self.relays.values())
        assert sum(self.ports.values()) == 1
        self.events.append(("flash", board["name"]))
        if self.fail == "flash":
            raise RuntimeError("upload failure")

    def measure(self, board):
        assert not any(self.ports.values())
        assert sum(self.relays.values()) == 1
        assert self.relays[board["relay"]]
        self.events.append(("measure", board["name"]))
        if self.fail == "measure":
            raise KeyboardInterrupt

    def close(self):
        self.events.append(("close",))

    def event(self, *args, **kwargs):
        self.events.append(("cleanup_error",))


class AutomationTests(unittest.TestCase):
    def config(self):
        return run.load_config(run.ROOT / "automation/config.example.json")

    def test_sequence_one_to_three_boards_with_four_relays(self):
        for count in (1, 2, 3):
            with self.subTest(count=count):
                config = self.config()
                config["connected_boards"] = config["connected_boards"][:count]
                hardware = FakeHardware()
                run.sequence(config, hardware)
                self.assertEqual(hardware.events[1:5], [("relay", n, False) for n in range(4)])
                flashes = [i for i, e in enumerate(hardware.events) if e[0] == "flash"]
                measurements = [i for i, e in enumerate(hardware.events) if e[0] == "measure"]
                self.assertEqual(len(flashes), count)
                self.assertEqual(len(measurements), count)
                self.assertLess(max(flashes), min(measurements))
                self.assertFalse(any(hardware.relays.values()))
                self.assertFalse(any(hardware.ports.values()))

    def test_upload_error_and_interrupt_disconnect_everything(self):
        for failure, error in (("flash", RuntimeError), ("measure", KeyboardInterrupt)):
            with self.subTest(failure=failure):
                hardware = FakeHardware(failure)
                with self.assertRaises(error):
                    run.sequence(self.config(), hardware)
                self.assertFalse(any(hardware.relays.values()))
                self.assertFalse(any(hardware.ports.values()))
                self.assertEqual(hardware.events[-1], ("close",))
                if failure == "flash":
                    self.assertFalse(any(e[0] == "measure" for e in hardware.events))

    def test_config_rejects_duplicate_or_out_of_range_mappings(self):
        base = self.config()
        base["sketch"] = str(run.ROOT / "automation/deep_sleep/deep_sleep.ino")
        for field, value in (("relay", 4), ("relay", 1), ("usb_port", 2), ("com", "COM18")):
            with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as folder:
                config = copy.deepcopy(base)
                config["connected_boards"][0][field] = value
                path = Path(folder) / "config.json"
                path.write_text(json.dumps(config))
                with self.assertRaises(ValueError):
                    run.load_config(path)

    def test_ykush_serial_and_model_command(self):
        config = self.config()
        config["ykush_model_argument"] = "ykush"
        with tempfile.TemporaryDirectory() as folder:
            hardware = run.Hardware(config, Path(folder))
            with patch.object(run, "run_command", side_effect=["", "Downstream port 2 is OFF"]) as command:
                hardware.usb(2, False)
            expected = [config["ykush_cmd"], "ykush", "-s", config["ykush_serial"]]
            self.assertEqual(command.call_args_list[0].args[0], expected + ["-d", "2"])
            self.assertEqual(command.call_args_list[1].args[0], expected + ["-g", "2"])

    def test_numato_readback_required(self):
        hardware = run.Hardware(self.config(), None)
        hardware.command = Mock(side_effect=["relay off 3\r\n>", "relay read 3\r\noff\r\n>"])
        hardware.relay(3, False)
        hardware.command = Mock(side_effect=[">", "relay read 3\r\non\r\n>"])
        with self.assertRaisesRegex(RuntimeError, "did not confirm"):
            hardware.relay(3, False)

    def test_automation_calls_standalone_uploader(self):
        config = self.config()
        with tempfile.TemporaryDirectory() as folder:
            hardware = run.Hardware(config, Path(folder))
            with patch.object(run, "run_command") as command:
                hardware.flash(config["connected_boards"][0])
            args = command.call_args.args[0]
            self.assertEqual(args[:6], [sys.executable, "-u", str(run.ROOT / "upload.py"), "nodemcu", "COM7", config["sketch"]])

    def test_upload_profile_is_selected_per_board(self):
        config = self.config()
        config["connected_boards"][1]["upload_profile"] = "second_profile"
        with tempfile.TemporaryDirectory() as folder:
            hardware = run.Hardware(config, Path(folder))
            with patch.object(run, "run_command") as command:
                for board in config["connected_boards"][:2]:
                    hardware.flash(board)
            self.assertEqual([call.args[0][3] for call in command.call_args_list],
                             ["nodemcu", "second_profile"])

    def test_subprocess_failure_stops_sequence(self):
        with self.assertRaisesRegex(RuntimeError, "Command failed"):
            run.run_command([sys.executable, "-c", "raise SystemExit(7)"], 5)

    def test_subprocess_timeout_terminates_process(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            run.run_command([sys.executable, "-c", "import time; time.sleep(60)"], .2)


if __name__ == "__main__":
    unittest.main()
