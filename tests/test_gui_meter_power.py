"""Manual OUT stays on until OFF, capture handoff or window shutdown."""
import unittest
from unittest.mock import Mock, call, patch

from automation.backend.api import DesktopApi
from automation.backend.meter_power import MeterPower


class MeterPowerTests(unittest.TestCase):
    @patch("automation.backend.meter_power.identify_device")
    @patch("automation.backend.meter_power.Device")
    def test_on_keeps_control_connection_and_off_closes_it(self, device, identify):
        power = MeterPower()
        result = power.set("COM18", "3.3", True)
        self.assertTrue(result["enabled"])
        self.assertEqual(device.return_value.command.call_args_list,
                         [call("htc"), call("pwr off"), call("volt vout 3300m"), call("pwr vout on")])
        device.return_value.close.assert_not_called()
        identify.assert_called_once_with(device.return_value)
        power.set("COM18", "invalid voltage is irrelevant to OFF", False)
        device.return_value.close.assert_called_once_with()
        device.assert_called_once_with("COM18")

    @patch("automation.backend.meter_power.identify_device")
    @patch("automation.backend.meter_power.Device")
    def test_protocol_failure_closes_meter(self, device, identify):
        device.return_value.command.side_effect = RuntimeError("No acknowledgement")
        with self.assertRaisesRegex(RuntimeError, "No acknowledgement"):
            MeterPower().set("COM18", 3.3, True)
        device.return_value.close.assert_called_once_with()

    def test_active_capture_blocks_manual_commands(self):
        api = DesktopApi(Mock())
        api._capture = Mock()
        api._capture.status.return_value = {"running": True}
        api._meter_power = Mock()
        with self.assertRaisesRegex(RuntimeError, "during capture"):
            api.set_meter_power("COM18", "3.3", True)
        api._meter_power.set.assert_not_called()

    def test_capture_releases_manual_connection_before_starting(self):
        api = DesktopApi(Mock())
        actions = Mock()
        api._capture = actions.capture
        api._meter_power = actions.power
        api._capture.status.return_value = {"running": False}
        config = {"port": "COM18"}
        api.start_capture(config)
        self.assertEqual(actions.mock_calls, [call.capture.status(), call.power.close(), call.capture.start(config)])
