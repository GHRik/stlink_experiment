"""GUI configuration round-trip through the real HIL runner, without hardware."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

from automation.backend.api import DesktopApi
from automation.backend.capture import CaptureProcess
from automation.backend.hil import hil_configuration
from automation.HIL import run


def gui_configuration():
    sketch = str(run.ROOT / "automation/HIL/example/example.ino")
    return dict(port="COM18", name="energy_test", description="NodeMCU test",
                repeats="10", seconds="100", hz="1000", voltage="3.3",
                warmup_seconds="180", off_seconds="1", controller="C:/scripts/control.py",
                hub=dict(driver="ykush", serial="TEST123"),
                relay=dict(driver="numato", port="COM19"),
                boards=[dict(upload_profile="nodemcu", sketch=sketch, com="COM22",
                             ykush_usb_port=3, relay=3),
                        dict(upload_profile="nodemcu", sketch=sketch, com="COM23",
                             ykush_usb_port=1, relay=0)])


class HilGuiTests(unittest.TestCase):
    @patch('automation.backend.hil.resolve_command', return_value='ykushcmd')
    def test_empty_name_uses_profile_and_sketch_stem(self, resolve):
        gui = gui_configuration()
        gui['name'] = ' '
        gui['boards'][0].update(sketch=r'C:\firmware\Blink.ino', dut=3)
        config = hil_configuration(gui, 'ykushcmd')
        self.assertRegex(config['connected_boards'][0]['name'],
                         r'^HIL_\d{8}_\d{6}_nodemcu_Blink_DUT3$')

    @patch("automation.backend.hil.resolve_command", return_value="ykushcmd")
    def test_generated_configuration_runs_through_actual_cli_dry_run(self, resolve):
        config = hil_configuration(gui_configuration(), "ykushcmd")
        runner = CaptureProcess()
        runner.start({}, command=[sys.executable, "-u", "-m", "automation.backend.hil_worker",
                                   json.dumps(config), "--dry-run"])
        try:
            runner._thread.join(timeout=20)
            result = runner.status()
            output = "\n".join(result["lines"])
            self.assertFalse(result["running"], output)
            self.assertEqual(result["returncode"], 0, output)
            self.assertRegex(output, r"energy_test_\d{8}_\d{6}_DUT1")
            self.assertRegex(output, r"energy_test_\d{8}_\d{6}_DUT2")
            self.assertIn("'port': 3", output)
            self.assertIn("'controller': 'C:/scripts/control.py'", output)
            self.assertEqual(config["connected_boards"][0]["relay"], 3)
        finally:
            runner.close()

    @patch("automation.backend.hil.resolve_command", return_value="ykushcmd")
    def test_api_releases_manual_meter_and_starts_hil_worker(self, resolve):
        api = DesktopApi(Mock())
        api._capture = Mock()
        api._capture.start.return_value = {}
        api._capture.status.return_value = {"running": False}
        api._meter_power = Mock()
        api.start_hil(gui_configuration())
        api._meter_power.close.assert_called_once()
        command = api._capture.start.call_args.kwargs["command"]
        self.assertEqual(command[:4], [sys.executable, "-u", "-m", "automation.backend.hil_worker"])
        self.assertEqual(json.loads(command[4])["stlink"]["com"], "COM18")

    def test_optional_controller_is_forwarded_by_existing_measurement_command(self):
        config = run.load_config(run.ROOT / "automation/HIL/config.example.jsonc")
        config["measurement"]["controller"] = "C:/scripts/control.py"
        hardware = run.Hardware(config, Path("unused"))
        hardware.event = Mock()
        with patch("pathlib.Path.open"), patch("automation.HIL.run.run_command") as command:
            hardware.measure(config["connected_boards"][0])
        args = command.call_args.args[0]
        self.assertEqual(args[-2:], ["--controller", "C:/scripts/control.py"])
