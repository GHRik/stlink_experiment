import subprocess
import unittest
from unittest.mock import Mock, call

from automation.backend.hubs import Hub, Ykush, Ykush3, YkushXs, create_hub


class HubTests(unittest.TestCase):
    def test_read_states_does_not_switch_ports(self):
        for cls, status, suffix in ((Ykush, 'Downstream port 1 is ON', ['-g', '1']),
                                    (Ykush3, 'Port 1 OFF', ['-g', '1']),
                                    (YkushXs, 'Downstream port is ON', ['-g'])):
            with self.subTest(driver=cls.__name__):
                command = Mock(return_value=status)
                hub = cls('ykushcmd', 'SERIAL', [1], command_runner=command)
                self.assertEqual(hub.get(1), status.endswith('ON'))
                self.assertEqual(command.call_args.args[0][-len(suffix):], suffix)
                self.assertEqual(command.call_count, 1)

    def test_xs_commands_have_no_port_argument(self):
        command = Mock(side_effect=["", "Downstream port is OFF", "", "Downstream port is ON"])
        hub = create_hub(dict(driver="ykushxs", cmd="ykushcmd", serial="XS123", ports=[1]), command)
        self.assertIsInstance(hub, YkushXs)
        hub.set(1, False)
        hub.set(1, True)
        prefix = ["ykushcmd", "ykushxs", "-s", "XS123"]
        self.assertEqual(command.call_args_list, [call(prefix + ["-d"], 15), call(prefix + ["-g"], 15),
                                                call(prefix + ["-u"], 15), call(prefix + ["-g"], 15)])
        command.reset_mock()
        with self.assertRaises(ValueError):
            hub.set(2, True)
        command.assert_not_called()

    def test_xs_rejects_multiport_configuration_and_wrong_readback(self):
        command = Mock(side_effect=["", "Downstream port is OFF"])
        with self.assertRaises(ValueError):
            YkushXs("ykushcmd", "XS123", [1, 2], command)
        with self.assertRaisesRegex(RuntimeError, "not confirmed"):
            YkushXs("ykushcmd", "XS123", [1], command).set(1, True)

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

    def test_original_ykush_selects_model_explicitly(self):
        command = Mock(side_effect=["", "Downstream port 1 is ON"])
        hub = create_hub(dict(driver="ykush", cmd="ykushcmd", serial="SERIAL", ports=[1]), command)
        self.assertIsInstance(hub, Ykush)
        hub.set(1, True)
        self.assertEqual(command.call_args_list[0], call(["ykushcmd", "ykush", "-s", "SERIAL", "-u", "1"], 15))

    def test_ykush3_native_readback(self):
        for enabled, status in ((True, "Port 3 ON\n"), (False, "Port 3 OFF\n")):
            with self.subTest(enabled=enabled):
                command = Mock(side_effect=["", status])
                hub = Ykush3("ykushcmd", "Y3N14729", [3], command)
                hub.set(3, enabled)
                self.assertEqual(hub.last_status, status.strip())

    def test_ykush3_rejects_wrong_socket_or_state(self):
        for status in ("Port 2 OFF", "Port 3 ON", "Port 13 OFF", "OFF"):
            with self.subTest(status=status):
                command = Mock(side_effect=["", status])
                with self.assertRaisesRegex(RuntimeError, "not confirmed"):
                    Ykush3("ykushcmd", "Y3N14729", [3], command).set(3, False)

    def test_readback_for_wrong_port_is_rejected_even_if_state_matches(self):
        for response in ('Downstream port 15 is OFF', 'Downstream port 1 is OFF', 'OFF'):
            command = Mock(side_effect=['', response])
            event = Mock()
            hub = create_hub(dict(driver='ykush', cmd='ykushcmd', serial='TEST', ports=[3]), command, event)
            with self.subTest(response=response), self.assertRaisesRegex(RuntimeError, 'not confirmed'):
                hub.set(3, False)
            event.assert_not_called()

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
