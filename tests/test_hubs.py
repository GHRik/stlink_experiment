import subprocess
import unittest
from unittest.mock import Mock, call

from automation.HIL.hubs import Hub, Ykush, Ykush3, create_hub


class HubTests(unittest.TestCase):
    def test_ykush3_selects_subcommand_serial_and_port(self):
        command = Mock(side_effect=["", "Downstream port 2 is OFF", "", "Downstream port 1 is ON"])
        hub = Ykush3("path with spaces/ykushcmd.exe", "SERIAL", [1, 2, 3], command)
        self.assertIsInstance(hub, Hub)
        hub.set(2, False)
        hub.set(1, True)
        prefix = ["path with spaces/ykushcmd.exe", "ykush3", "-s", "SERIAL"]
        self.assertEqual(command.call_args_list, [
            call(prefix + ["-d", "2"], 15), call(prefix + ["-g", "2"], 15),
            call(prefix + ["-u", "1"], 15), call(prefix + ["-g", "1"], 15)])

    def test_original_ykush_retains_legacy_syntax(self):
        command = Mock(side_effect=["", "Downstream port 1 is ON"])
        hub = create_hub(dict(driver="ykush", cmd="ykushcmd", serial="SERIAL", ports=[1]), command)
        self.assertIsInstance(hub, Ykush)
        hub.set(1, True)
        self.assertEqual(command.call_args_list[0], call(["ykushcmd", "-s", "SERIAL", "-u", "1"], 15))

    def test_failed_readback_invalid_port_and_cli_errors(self):
        command = Mock(side_effect=["", "Downstream port 1 is OFF"])
        hub = Ykush3("ykushcmd", "SERIAL", [1], command)
        with self.assertRaisesRegex(RuntimeError, "not confirmed"):
            hub.set(1, True)
        command.reset_mock(side_effect=True)
        with self.assertRaises(ValueError):
            hub.set(2, True)
        command.assert_not_called()
        command.side_effect = subprocess.CalledProcessError(1, "ykushcmd")
        with self.assertRaises(subprocess.CalledProcessError):
            hub.set(1, True)
        self.assertEqual(command.call_count, 1)

    def test_factory_validates_settings_without_hardware(self):
        base = dict(driver="ykush3", cmd="ykushcmd", serial="SERIAL", ports=[1, 2, 3])
        command = Mock()
        hub = create_hub(base, command)
        self.assertIsInstance(hub, Ykush3)
        hub.open()
        hub.close()
        command.assert_not_called()
        for override in (dict(driver="other"), dict(ports=[1, 1]), dict(ports=[4]),
                         dict(serial=""), dict(model_argument="")):
            with self.subTest(override=override), self.assertRaises(ValueError):
                create_hub(dict(base, **override), command)


if __name__ == "__main__":
    unittest.main()
