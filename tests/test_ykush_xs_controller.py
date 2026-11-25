"""Exercise the controller schedule and stop cleanup without switching hardware."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from automation.controllers import ykush_xs


class YkushControllerTests(unittest.TestCase):
    def test_five_second_phases_and_stop_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            stop = Path(folder) / 'stop'
            clock = [0.0]
            actions = []
            hub = Mock()

            def switch(port, enabled):
                actions.append((clock[0], port, enabled))
                if len(actions) == 3:
                    stop.touch()

            def sleep(seconds):
                clock[0] += seconds

            hub.set.side_effect = switch
            with patch.dict(ykush_xs.os.environ, {'STLINK_STOP_FILE': str(stop), 'YKUSH_XS_SERIAL': 'TEST'}), \
                 patch.object(ykush_xs, 'resolve_command', return_value='ykushcmd'), \
                 patch.object(ykush_xs, 'YkushXs', return_value=hub), \
                 patch.object(ykush_xs.time, 'monotonic', side_effect=lambda: clock[0]), \
                 patch.object(ykush_xs.time, 'sleep', side_effect=sleep), \
                 patch.object(ykush_xs, 'emit'):
                ykush_xs.main()
            self.assertEqual([state for _, _, state in actions], [True, False, True, False])
            self.assertAlmostEqual(actions[1][0], 5)
            self.assertAlmostEqual(actions[2][0], 10)
            hub.close.assert_called_once()

    def test_single_hub_is_discovered_and_remains_off_if_stop_is_already_requested(self):
        with tempfile.TemporaryDirectory() as folder:
            stop = Path(folder) / 'stop'
            stop.touch()
            with patch.dict(ykush_xs.os.environ, {'STLINK_STOP_FILE': str(stop), 'YKUSH_XS_SERIAL': ''}), \
                 patch.object(ykush_xs, 'resolve_command', return_value='ykushcmd'), \
                 patch.object(ykush_xs, 'available_hubs', return_value=[{'serial': 'XS123'}]), \
                 patch.object(ykush_xs, 'YkushXs') as factory, patch.object(ykush_xs, 'emit'):
                ykush_xs.main()
            factory.assert_called_once_with('ykushcmd', 'XS123', [1])
            factory.return_value.set.assert_called_once_with(1, False)
