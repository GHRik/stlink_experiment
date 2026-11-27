"""GUI capture delegates arguments and diagnostics to the measurement CLI."""
import io
from pathlib import Path
import sys
import time
import tempfile
import unittest
from unittest.mock import Mock, patch

from automation.backend.capture import CaptureProcess, capture_command
from automation.backend.api import DesktopApi


def configuration():
    return {"port": "COM18", "name": "sleep_test", "description": "NodeMCU; deep sleep",
            "repeats": "10", "seconds": "100", "hz": "1000", "voltage": "3.3",
            "warmup_seconds": "180", "off_seconds": "1"}


class CaptureCommandTests(unittest.TestCase):
    def test_upload_uses_existing_runner_and_arduino_upload_module(self):
        api = DesktopApi(Mock())
        api._capture = Mock()
        api._capture.status.return_value = {"running": False}
        api._meter_power = Mock()
        api.start_upload("nodemcu", "COM22", "C:/my sketches/example.ino")
        api._meter_power.close.assert_called_once()
        api._capture.start.assert_called_once_with({}, command=[sys.executable, "-u", "-m",
            "automation.backend.upload", "nodemcu", "COM22", "C:/my sketches/example.ino"])

    def test_maps_gui_fields_to_existing_cli_arguments(self):
        command = capture_command(configuration())
        self.assertEqual(command[:5], [sys.executable, "-u", "-m", "automation.backend.capture_worker", "capture"])
        self.assertEqual(command[5:], ["--port", "COM18", "--name", "sleep_test", "--notes",
                         "NodeMCU; deep sleep", "--repeats", "10", "--seconds", "100",
                         "--hz", "1000", "--voltage", "3.3", "--warmup-seconds", "180", "--off-seconds", "1"])

    def test_controller_path_and_description_remain_single_arguments(self):
        config = dict(configuration(), controller="C:/folder with spaces/control.py", description='test; "quoted"')
        command = capture_command(config)
        self.assertEqual(command[-2:], ["--controller", config["controller"]])
        self.assertEqual(command[command.index("--notes") + 1], 'test; "quoted"')


class CaptureProcessTests(unittest.TestCase):
    @patch("automation.backend.capture.subprocess.Popen")
    def test_streams_output_and_preserves_exit_status(self, popen):
        process = popen.return_value
        process.stdout = io.StringIO("first line\nCLI error\n")
        process.wait.return_value = 1
        runner = CaptureProcess()
        runner.start(configuration())
        runner._thread.join(timeout=2)
        result = runner.status(after=1)
        self.assertFalse(result["running"])
        self.assertEqual(result["returncode"], 1)
        self.assertEqual(result["lines"], ["CLI error"])
        self.assertEqual(result["cursor"], 2)
        self.assertEqual(popen.call_args.kwargs["cwd"], Path(__file__).resolve().parents[1])
        self.assertNotIn("shell", popen.call_args.kwargs)

    @patch("automation.backend.capture.Thread")
    @patch("automation.backend.capture.subprocess.Popen")
    def test_rejects_concurrent_capture_and_stop_requests_cleanup(self, popen, thread):
        popen.return_value.poll.return_value = None
        runner = CaptureProcess()
        runner.start(configuration())
        with self.assertRaisesRegex(RuntimeError, "already running"):
            runner.start(configuration())
        runner.stop()
        runner.stop()
        self.assertTrue(runner._stop_file.exists())
        self.assertTrue(runner.status()["stopping"])
        thread.call_args.kwargs["args"][1].cleanup()

    def test_real_cli_validation_errors_reach_the_gui_without_accessing_hardware(self):
        runner = CaptureProcess()
        runner.start(dict(configuration(), name="invalid test name"))
        runner._thread.join(timeout=20)
        result = runner.status()
        self.assertFalse(result["running"])
        self.assertEqual(result["returncode"], 1)
        self.assertIn("--name", "\n".join(result["lines"]))
        self.assertIn("ERROR:", "\n".join(result["lines"]))

    def test_stop_runs_worker_cleanup_without_hardware(self):
        code = """import sys, time
from automation.backend import capture_worker
def fake_measurement():
    print('READY', flush=True)
    try:
        while True:
            time.sleep(0.1)
    finally:
        print('CLEANED', flush=True)
capture_worker.measure_main = fake_measurement
sys.exit(capture_worker.main())
"""
        runner = CaptureProcess()
        with patch("automation.backend.capture.capture_command", return_value=[sys.executable, "-u", "-c", code]):
            runner.start(configuration())
        try:
            deadline = time.monotonic() + 15
            while "READY" not in runner.status()["lines"] and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertIn("READY", runner.status()["lines"])
            runner.stop()
            runner._thread.join(timeout=10)
            self.assertFalse(runner.status()["running"])
            self.assertEqual(runner.status()["returncode"], 130)
            self.assertIn("CLEANED", runner.status()["lines"])
        finally:
            runner.close()

    def test_window_close_stops_capture_and_its_controller(self):
        code = '''import sys,time,os
from pathlib import Path
from automation.backend import capture_worker
from src.measurement_controller import MeasurementController
def measure():
    root=Path(os.environ['STLINK_GUI_STOP_FILE']).parent
    script=root/'controller.py'
    script.write_text("import os,time\\nfrom pathlib import Path\\np=Path(os.environ['STLINK_STOP_FILE'])\\nwhile not p.exists(): time.sleep(.05)\\nprint('controller cleaned',flush=True)\\n")
    controller=MeasurementController(script,root,60)
    controller.start()
    print('READY',flush=True)
    try:
        while True: time.sleep(.05)
    finally:
        outcome=controller.close()
        print('CONTROLLER_CLOSED',outcome['returncode'],outcome['forced_stop'],flush=True)
sys.exit(capture_worker.main(measure))
'''
        runner=CaptureProcess()
        runner.start({},command=[sys.executable,'-u','-c',code])
        try:
            deadline=time.monotonic()+15
            while 'READY' not in runner.status()['lines'] and time.monotonic()<deadline:
                time.sleep(.05)
            self.assertIn('READY',runner.status()['lines'])
            self.assertTrue(runner.close())
            self.assertFalse(runner._thread.is_alive())
            self.assertIsNotNone(runner._process.poll())
            self.assertIn('CONTROLLER_CLOSED 0 False',runner.status()['lines'])
        finally:
            runner.close()

    def test_close_escalates_when_worker_ignores_stop(self):
        from unittest.mock import Mock
        runner = CaptureProcess()
        runner._running = True
        runner._process = Mock()
        runner._process.pid = 12345
        runner._process.poll.return_value = None
        runner._thread = Mock()
        runner._thread.is_alive.return_value = True
        with tempfile.TemporaryDirectory() as directory:
            runner._stop_file = Path(directory) / 'stop'
            def joined(timeout):
                if timeout == 5:
                    runner._running = False
            runner._thread.join.side_effect = joined
            with patch('automation.backend.capture.subprocess.run') as terminate:
                self.assertTrue(runner.close())
            if sys.platform == 'win32':
                self.assertEqual(terminate.call_args.args[0],
                                 ['taskkill', '/PID', '12345', '/T', '/F'])
            else:
                runner._process.kill.assert_called_once()
            runner._process.wait.assert_called_once_with(timeout=10)
