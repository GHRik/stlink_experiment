import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from automation.HIL import run


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
    def test_board_notes_are_optional(self):
        config = run.read_config(run.ROOT / 'automation/HIL/config.example.jsonc')
        for board in config['connected_boards']:
            board.pop('notes')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps(config))
            loaded = run.load_config(path)
        self.assertTrue(all(board['notes'] == '' for board in loaded['connected_boards']))

    def test_config_comments_do_not_change_string_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.jsonc"
            path.write_text('// Description\n{\n  // Another comment\n  "value": "https://example.org/a//b"\n}\n')
            self.assertEqual(run.read_config(path), {"value": "https://example.org/a//b"})

    def config(self):
        return run.load_config(run.ROOT / "automation/HIL/config.example.jsonc")

    def test_legacy_numato_config_remains_supported(self):
        data = run.read_config(run.ROOT / "automation/HIL/config.example.jsonc")
        relay = data.pop("relay_controller")
        data["numato"] = dict(controller_port=relay["port"], ports=relay["channels"],
                              channel_digits=relay["channel_digits"])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps(data))
            self.assertEqual(run.load_config(path)["relay_controller"], relay)

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
        for field, value in (("relay", 4), ("relay", 1), ("ykush_usb_port", 2), ("com", "COM18")):
            with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as folder:
                config = copy.deepcopy(base)
                config["connected_boards"][0][field] = value
                path = Path(folder) / "config.json"
                path.write_text(json.dumps(config))
                with self.assertRaises(ValueError):
                    run.load_config(path)

    def test_ykush_serial_and_model_command(self):
        config = self.config()
        config["hub"]["model_argument"] = "ykush"
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(run, "run_command", side_effect=["", "Downstream port 2 is OFF"]) as command:
                hardware = run.Hardware(config, Path(folder))
                hardware.usb(2, False)
            expected = [config["hub"]["cmd"], "ykush", "-s", config["hub"]["serial"]]
            self.assertEqual(command.call_args_list[0].args[0], expected + ["-d", "2"])
            self.assertEqual(command.call_args_list[1].args[0], expected + ["-g", "2"])

    def test_legacy_ykush_section_and_ykush3_driver(self):
        data = run.read_config(run.ROOT / "automation/HIL/config.example.jsonc")
        hub = data.pop("hub")
        hub.pop("driver")
        hub["model_argument"] = "ykush3"
        data["ykush"] = hub
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps(data))
            config = run.load_config(path)
            self.assertEqual(config["hub"]["driver"], "ykush3")
            with patch.object(run, "run_command", side_effect=["", "Downstream port 1 is ON"]) as command:
                hardware = run.Hardware(config, Path(folder))
                hardware.usb(1, True)
            self.assertEqual(command.call_args_list[0].args[0][1], "ykush3")

    def test_lcus2_configuration_selects_individual_channels(self):
        config = run.load_config(run.ROOT / "automation/HIL/config.lcus2.json")
        self.assertEqual(config["relay_controller"]["driver"], "lcus2")
        self.assertEqual(config["relay_controller"]["channels"], 2)
        hardware = FakeHardware()
        hardware.relays = {0: True, 1: True}
        run.sequence(config, hardware)
        self.assertEqual(hardware.events[1:3], [("relay", 0, False), ("relay", 1, False)])
        self.assertEqual([event for event in hardware.events if event[0] == "relay" and event[2]],
                         [("relay", 0, True)])

    def test_automation_calls_standalone_uploader(self):
        config = self.config()
        with tempfile.TemporaryDirectory() as folder:
            hardware = run.Hardware(config, Path(folder))
            with patch.object(run, "run_command") as command:
                hardware.flash(config["connected_boards"][0])
            args = command.call_args.args[0]
            self.assertEqual(args[:6], [sys.executable, "-u", str(run.ROOT / "automation/backend/upload.py"), "nodemcu", "COM7", config["connected_boards"][0]["sketch"]])

    def test_measurement_uses_src_module_from_repository_root(self):
        config = self.config()
        with tempfile.TemporaryDirectory() as folder:
            hardware = run.Hardware(config, Path(folder))
            with patch.object(run, "run_command") as command:
                hardware.measure(config["connected_boards"][0])
            self.assertEqual(command.call_args.args[0][:4],
                             [sys.executable, "-m", "src.stlink_measure", "capture"])
            self.assertEqual(command.call_args.kwargs["cwd"], run.ROOT)

    def test_sketch_is_selected_and_resolved_per_board(self):
        data = run.read_config(run.ROOT / "automation/HIL/config.example.jsonc")
        data["connected_boards"][0]["sketch"] = "first/first.ino"
        data["connected_boards"][1]["sketch"] = "second/second.ino"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps(data))
            config = run.load_config(path)
            hardware = run.Hardware(config, Path(folder))
            with patch.object(run, "run_command") as command:
                for board in config["connected_boards"][:2]:
                    hardware.flash(board)
            self.assertEqual([call.args[0][5] for call in command.call_args_list],
                             [str(Path(folder) / "first/first.ino"), str(Path(folder) / "second/second.ino")])

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
