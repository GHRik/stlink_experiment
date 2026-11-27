"""Desktop switching must address a selected hub and confirm CLI readback."""
import unittest
from unittest.mock import Mock, call, patch

from automation.backend.hub_control import HubControl


class HubControlTests(unittest.TestCase):
    @patch("automation.backend.hub_control.resolve_command", return_value="ykushcmd")
    @patch("automation.backend.hubs._run")
    def test_xs_uses_only_its_single_output(self, run, resolve):
        run.side_effect = ["", "Downstream port is ON"]
        self.assertTrue(HubControl().set_port("ykushxs", "ykushcmd", "XS123", 1, True)["enabled"])
        self.assertEqual(run.call_args_list, [call(["ykushcmd", "ykushxs", "-s", "XS123", "-u"], 15),
                                              call(["ykushcmd", "ykushxs", "-s", "XS123", "-g"], 15)])
        run.reset_mock()
        with self.assertRaises(ValueError):
            HubControl().set_port("ykushxs", "ykushcmd", "XS123", 2, True)
        run.assert_not_called()

    @patch("automation.backend.hub_control.resolve_command", return_value="C:/tools/ykushcmd.exe")
    @patch("automation.backend.hubs._run")
    def test_selected_legacy_hub_and_physical_socket(self, run, resolve):
        run.side_effect = ["", "Downstream port 2 is OFF"]
        result = HubControl().set_port("ykush", "ykushcmd", "YK21493", 2, False)
        prefix = ["C:/tools/ykushcmd.exe", "ykush", "-s", "YK21493"]
        self.assertEqual(run.call_args_list, [call(prefix + ["-d", "2"], 15),
                                              call(prefix + ["-g", "2"], 15)])
        self.assertEqual(result, {"serial": "YK21493", "port": 2, "enabled": False,
                                  "readback": "Downstream port 2 is OFF"})

    @patch("automation.backend.hub_control.resolve_command", return_value="ykushcmd")
    @patch("automation.backend.hubs._run")
    def test_selected_ykush3(self, run, resolve):
        run.side_effect = ["", "Downstream port 1 is ON"]
        HubControl().set_port("ykush3", "ykushcmd", "YK00009", 1, True)
        self.assertEqual(run.call_args_list, [
            call(["ykushcmd", "ykush3", "-s", "YK00009", "-u", "1"], 15),
            call(["ykushcmd", "ykush3", "-s", "YK00009", "-g", "1"], 15)])

    @patch("automation.backend.hub_control.resolve_command", return_value="ykushcmd")
    @patch("automation.backend.hubs._run")
    def test_wrong_readback_is_not_reported_as_success(self, run, resolve):
        run.side_effect = ["", "Downstream port 1 is OFF"]
        with self.assertRaisesRegex(RuntimeError, "not confirmed"):
            HubControl().set_port("ykush", "ykushcmd", "YK17125", 1, True)

    @patch("automation.backend.hub_control.create_hub")
    def test_missing_serial_or_invalid_socket_does_not_touch_hardware(self, create):
        control = HubControl()
        for serial, port, enabled in (("", 1, True), ("  ", 1, True),
                                       ("YK1", 4, True), ("YK1", 1, "on")):
            with self.subTest(serial=serial, port=port), self.assertRaises(ValueError):
                control.set_port("ykush", "ykushcmd", serial, port, enabled)
        create.assert_not_called()

    @patch("automation.backend.hub_control.resolve_command", return_value="ykushcmd")
    @patch("automation.backend.hub_control.create_hub")
    def test_driver_is_closed_after_failure(self, create, resolve):
        create.return_value.set.side_effect = RuntimeError("USB error")
        with self.assertRaisesRegex(RuntimeError, "USB error"):
            HubControl().set_port("ykush", "ykushcmd", "YK17125", 1, True)
        create.return_value.close.assert_called_once_with()
