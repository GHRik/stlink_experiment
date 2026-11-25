import argparse
import csv
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from src.measurement_controller import MeasurementController
from src import stlink_protocol
from tests.test_stlink_measure import FakeDevice


class ControllerTests(unittest.TestCase):
    def test_example_process_records_events_and_stops(self):
        with tempfile.TemporaryDirectory(prefix="controller test ") as folder:
            root = Path(folder)
            controller = MeasurementController(Path(__file__).resolve().parents[1] / "automation/controllers/example.py", root, 10)
            controller.start()
            try:
                deadline = time.monotonic() + 5
                events = root / "controller_events.csv"
                while not events.exists() or len(events.read_text().splitlines()) < 3:
                    controller.check()
                    if time.monotonic() > deadline:
                        self.fail("Example controller did not produce events")
                    time.sleep(.02)
            finally:
                outcome = controller.close()
            self.assertEqual(outcome["returncode"], 0)
            self.assertFalse(outcome["forced_stop"])
            with events.open(encoding="utf-8") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(rows[0]["event"], "started")
            self.assertEqual(rows[-1]["event"], "stopped")
            self.assertIn("tick", [row["event"] for row in rows])

    def test_uncooperative_process_is_killed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = root / "uncooperative.py"
            script.write_text("import time\ntime.sleep(60)\n")
            controller = MeasurementController(script, root, 1)
            controller.start()
            outcome = controller.close()
            self.assertTrue(outcome["forced_stop"])
            self.assertIsNotNone(controller.process.poll())

    def test_failed_process_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = root / "failed.py"
            script.write_text("raise RuntimeError('test failure')\n")
            controller = MeasurementController(script, root, 1)
            controller.start()
            controller.process.wait(timeout=5)
            try:
                with self.assertRaisesRegex(RuntimeError, "Controller exited"):
                    controller.check()
            finally:
                outcome = controller.close()
            self.assertNotEqual(outcome["returncode"], 0)
            self.assertIn("test failure", (root / "controller.log").read_text())

    def test_capture_lifecycle_and_interruption(self):
        for interruption in (False, True):
            with self.subTest(interruption=interruption), tempfile.TemporaryDirectory() as folder:
                device = FakeDevice([b"ack start\r\n"] + [b"1000-05\r\n"] * 10 + [b"end\r\n"])
                args = argparse.Namespace(seconds=.1, hz=100, name="test", voltage=3.3,
                                          off_seconds=1, notes="fake", controller="example.py")
                path = Path(folder) / "repeat"
                with patch.object(stlink_protocol, "MeasurementController") as factory, patch.object(stlink_protocol.time, "sleep"):
                    controller = factory.return_value
                    controller.process = None

                    def start():
                        commands = [event["tx"] for event in device.events]
                        self.assertIn("calib", commands)
                        self.assertEqual(commands[-1], "start")
                        controller.process = object()

                    controller.start.side_effect = start
                    controller.close.return_value = {"returncode": 0, "forced_stop": False}
                    if interruption:
                        controller.check.side_effect = KeyboardInterrupt
                    original_send = device.send
                    def send(command):
                        if command == "stop":
                            controller.request_stop.assert_called()
                        return original_send(command)
                    device.send = send
                    if interruption:
                        with self.assertRaises(KeyboardInterrupt):
                            stlink_protocol.capture_one(device, path, args, {}, 1)
                    else:
                        stlink_protocol.capture_one(device, path, args, {}, 1)
                    controller.start.assert_called_once()
                    controller.close.assert_called_once()
                metadata = json.loads((path / "metadata.json").read_text())
                self.assertEqual(metadata["status"], "invalid" if interruption else "valid")

    def test_calibration_failure_does_not_start_controller(self):
        with tempfile.TemporaryDirectory() as folder:
            device = FakeDevice([])
            original = device.command
            device.command = lambda command, **kw: "error calib" if command == "calib" else original(command, **kw)
            args = argparse.Namespace(seconds=.1, hz=100, name="test", voltage=3.3,
                                      off_seconds=1, notes="fake", controller="example.py")
            with patch.object(stlink_protocol, "MeasurementController") as factory, patch.object(stlink_protocol.time, "sleep"):
                factory.return_value.close.return_value = None
                with self.assertRaises(RuntimeError):
                    stlink_protocol.capture_one(device, Path(folder) / "repeat", args, {}, 1)
                factory.return_value.start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
