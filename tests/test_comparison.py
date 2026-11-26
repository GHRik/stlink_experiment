"""Numerical comparison and export use raw samples without changing the source."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from automation.backend.comparison import generate_comparison, ComparisonView


def session(root, name, currents):
    folder = root / name
    folder.mkdir()
    for index, current in enumerate(currents, 1):
        repeat = folder / f'repeat_{index:03d}'
        repeat.mkdir()
        (repeat / 'metadata.json').write_text(json.dumps(dict(status='valid', configuration='test',
            voltage_V=3.3, sampling_Hz=2, samples=4, requested_duration_s=2, board_notes='same firmware', identity={})))
        (repeat / 'samples.csv').write_text('sample_index;time_s;current_uA\n' +
            ''.join(f'{i};{i/2};{current*1000}\n' for i in range(4)))
    return folder


class ComparisonTests(unittest.TestCase):
    def test_mean_sample_sd_single_repeat_exclusion_and_export(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as work, TemporaryDirectory() as destination:
            root = Path(directory)
            first = session(root, 'DUT1', [10, 14])
            session(root, 'DUT2', [20])
            invalid = first / 'repeat_invalid'
            invalid.mkdir()
            (invalid / 'metadata.json').write_text('{"status":"invalid"}')
            before = {path: path.read_bytes() for path in root.rglob('*') if path.is_file()}
            rows = generate_comparison(root, ['DUT1', 'DUT2'], work)
            self.assertEqual(rows[0]['mean_mA'], 12)
            self.assertAlmostEqual(rows[0]['sd_mA'], 8**.5)
            self.assertAlmostEqual(rows[0]['energy_J'], .0792)
            self.assertEqual(rows[0]['excluded'], 1)
            self.assertIsNone(rows[1]['sd_mA'])
            self.assertIn('SD requires at least two valid repeats.', (Path(work) / 'comparison_statistics.svg').read_text(encoding='utf-8'))
            self.assertNotEqual(rows[0]['color'], rows[1]['color'])
            self.assertEqual(before, {path: path.read_bytes() for path in root.rglob('*') if path.is_file()})
            holder = Mock(name=work)
            holder.name = work
            view = ComparisonView(Mock(), holder)
            view._window = Mock()
            view._window.create_file_dialog.return_value = (destination,)
            saved = Path(view.save_figures())
            self.assertEqual(len(list(saved.glob('*.png'))), 2)
            self.assertEqual(len(list(saved.glob('*.svg'))), 2)
            for plot in saved.glob('*'):
                self.assertEqual(plot.read_bytes(), (Path(work) / plot.name).read_bytes())
            self.assertTrue(view.get_comparison()['images']['comparison_traces'].startswith('data:image/png;base64,'))
            view._window.create_file_dialog.return_value = None
            self.assertIsNone(view.save_figures())
            session(root, 'DUT3', [30, 32])
            generate_comparison(root, ['DUT1', 'DUT3'], work)
            self.assertNotIn('SD requires at least two valid repeats.', (Path(work) / 'comparison_statistics.svg').read_text(encoding='utf-8'))

    def test_requires_distinct_sessions_and_rejects_paths_outside_results(self):
        with TemporaryDirectory() as root, TemporaryDirectory() as work:
            for names in (['same','same'], ['../outside','second']):
                with self.subTest(names=names), self.assertRaises(ValueError):
                    generate_comparison(root, names, work)

    def test_rejects_mixed_measurement_conditions_inside_one_session(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as work:
            root = Path(directory)
            first = session(root, 'DUT1', [10, 14])
            session(root, 'DUT2', [20])
            path = first / 'repeat_002/metadata.json'
            meta = json.loads(path.read_text())
            meta['voltage_V'] = 3.0
            path.write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError, 'different voltage'):
                generate_comparison(root, ['DUT1','DUT2'], work)
