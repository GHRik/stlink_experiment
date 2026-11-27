"""GUI relay commands delegate to the existing driver without reimplementing it."""
import unittest
from unittest.mock import call, patch

from automation.backend.relay_control import RelayControl


class RelayControlTests(unittest.TestCase):
    @patch('automation.backend.relay_control.create_relay')
    def test_read_all_numato_channels_without_switching(self, factory):
        factory.return_value.channels = 4
        factory.return_value.get.side_effect = [True, False, True, False]
        self.assertEqual(RelayControl().read_states('numato', 'COM19'),
                         {'0': True, '1': False, '2': True, '3': False})
        factory.return_value.set.assert_not_called()
        factory.return_value.close.assert_called_once()

    @patch('automation.backend.relay_control.create_relay')
    def test_lcus2_has_no_readback(self, factory):
        self.assertEqual(RelayControl().read_states('lcus2', 'COM19'), {})
        factory.assert_not_called()

    @patch("automation.backend.relay_control.create_relay")
    def test_model_port_and_zero_based_channel_are_forwarded(self, factory):
        result = RelayControl().set_channel("lcus2", "COM19", 1, True)
        factory.assert_called_once_with({"driver": "lcus2", "port": "COM19", "channels": 2})
        self.assertEqual(factory.return_value.mock_calls, [call.open(), call.set(1, True), call.close()])
        self.assertEqual(result["confirmation"], "write_and_flush")

    @patch("automation.backend.relay_control.create_relay")
    def test_driver_error_is_propagated_and_port_is_closed(self, factory):
        factory.return_value.set.side_effect = RuntimeError("Driver error")
        with self.assertRaisesRegex(RuntimeError, "Driver error"):
            RelayControl().set_channel("numato", "COM22", 2, False)
        factory.return_value.close.assert_called_once_with()
