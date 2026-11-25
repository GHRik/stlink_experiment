"""Preview batching preserves peaks without changing the acquisition samples."""
import unittest
from unittest.mock import patch

from src.live_current import LiveCurrentPreview


class LiveCurrentTests(unittest.TestCase):
    @patch('src.live_current.emit')
    def test_1000_hz_bins_preserve_mean_and_single_sample_peak(self, emit):
        with patch.dict('os.environ', {'STLINK_GUI_EVENT_FILE': 'unused'}):
            preview = LiveCurrentPreview('test', 2, 1000)
        for index in range(500):
            preview.add(.15 if index == 7 else .01, index)
        self.assertEqual(emit.call_count, 1)
        points = emit.call_args.kwargs['points']
        self.assertEqual(len(points), 10)
        self.assertAlmostEqual(points[0][0], .0245)
        self.assertAlmostEqual(points[0][1], 12.8)
        self.assertEqual(points[0][2:], [10, 150])
        self.assertEqual(emit.call_args.kwargs['repeat'], 2)

    @patch('src.live_current.emit')
    def test_low_rate_and_final_partial_bin_are_delivered(self, emit):
        with patch.dict('os.environ', {'STLINK_GUI_EVENT_FILE': 'unused'}):
            slow = LiveCurrentPreview('slow', 1, 1)
            partial = LiveCurrentPreview('partial', 1, 1000)
        slow.add(.0001, 0)
        self.assertEqual(emit.call_args.kwargs['points'], [[0, .1, .1, .1]])
        partial.add(.02, 0)
        partial.add(.04, 1)
        partial.flush()
        self.assertEqual(emit.call_args.kwargs['points'], [[.0005, 30, 20, 40]])
        partial.flush()
        self.assertEqual(emit.call_count, 2)

    @patch('src.live_current.emit')
    def test_plain_cli_does_not_build_preview_data(self, emit):
        with patch.dict('os.environ', {}, clear=True):
            preview = LiveCurrentPreview('test', 1, 20000)
        for index in range(1000):
            preview.add(.01, index)
        preview.flush()
        emit.assert_not_called()
        self.assertEqual(preview.points, [])
