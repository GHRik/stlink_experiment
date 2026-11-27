import unittest
from unittest.mock import Mock, call, patch

from automation.backend.relays import Relay, NumatoRelay, Lcus2Relay, create_relay


class RelayTests(unittest.TestCase):
    def test_numato_channel_three_is_sent_without_an_offset(self):
        relay = NumatoRelay('COM19',4)
        relay.command=Mock(side_effect=['>','relay read 3\r\non\r\n>'])
        relay.set(3,True)
        self.assertEqual(relay.command.call_args_list,[call('relay on 3'),call('relay read 3')])

    def test_factory_and_invalid_settings(self):
        self.assertIsInstance(create_relay(dict(driver="numato", port="COM1", channels=4)), Relay)
        self.assertIsInstance(create_relay(dict(driver="lcus2", port="COM1", channels=2)), Lcus2Relay)
        for config in (dict(driver="other", port="COM1", channels=2),
                       dict(driver="lcus2", port="COM1", channels=3),
                       dict(driver="numato", port="COM1", channels=0)):
            with self.subTest(config=config), self.assertRaises(ValueError):
                create_relay(config)

    def test_lcus2_packets_switch_only_requested_channel(self):
        event = Mock()
        relay = Lcus2Relay("COM22", event=event)
        relay.serial = Mock()
        relay.serial.write.return_value = 4
        for channel, enabled in ((0, True), (0, False), (1, True), (1, False)):
            relay.set(channel, enabled)
        self.assertEqual(relay.serial.write.call_args_list, [
            call(bytes.fromhex("A0 01 01 A2")), call(bytes.fromhex("A0 01 00 A1")),
            call(bytes.fromhex("A0 02 01 A3")), call(bytes.fromhex("A0 02 00 A2"))])
        self.assertEqual(relay.serial.flush.call_count, 4)
        relay.serial.read.assert_not_called()
        relay.serial.read_until.assert_not_called()
        self.assertEqual(event.call_args.kwargs["confirmation"], "write_and_flush")

    def test_lcus2_short_write_or_flush_failure_propagates(self):
        relay = Lcus2Relay("COM22")
        relay.serial = Mock()
        relay.serial.write.return_value = 3
        with self.assertRaisesRegex(IOError, "Incomplete"):
            relay.set(0, True)
        relay.serial.write.return_value = 4
        relay.serial.flush.side_effect = OSError("USB disconnected")
        with self.assertRaisesRegex(OSError, "USB disconnected"):
            relay.set(0, True)

    def test_numato_requires_matching_readback(self):
        relay = NumatoRelay("COM19", 4)
        relay.command = Mock(side_effect=[">", "relay read 3\r\noff\r\n>"])
        relay.set(3, False)
        self.assertEqual(relay.command.call_args_list, [call("relay off 3"), call("relay read 3")])
        relay.command = Mock(side_effect=[">", "relay read 3\r\non\r\n>"])
        with self.assertRaisesRegex(RuntimeError, "did not confirm"):
            relay.set(3, False)

    def test_numato_serial_protocol_and_channel_format(self):
        relay = NumatoRelay("COM19", 4, channel_digits=3)
        relay.serial = Mock()
        relay.serial.write.side_effect = len
        relay.serial.read_until.side_effect = [b"relay on 001\r\n>", b"relay read 001\r\non\r\n>"]
        relay.set(1, True)
        self.assertEqual(relay.serial.write.call_args_list,
                         [call(b"relay on 001\r"), call(b"relay read 001\r")])
        relay.serial.read_until.side_effect = [b"error\r\n>"]
        with self.assertRaisesRegex(RuntimeError, "command failed"):
            relay.set(1, False)

    def test_port_lifecycle_and_channel_bounds(self):
        for relay, baudrate in ((NumatoRelay("COM19", 4), 19200), (Lcus2Relay("COM22"), 9600)):
            with self.subTest(relay=type(relay).__name__), patch("automation.backend.relays.serial.Serial") as connection:
                relay.open()
                connection.assert_called_once_with(relay.port, baudrate, timeout=2, write_timeout=3)
                with self.assertRaises(ValueError):
                    relay.set(relay.channels, True)
                connection.return_value.write.assert_not_called()
                relay.close()
                connection.return_value.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
