"""Numerical comparison and export use raw samples without changing the source."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from automation.backend.comparison import generate_comparison, ComparisonData, export_samples
from automation.backend.comparison_window import ComparisonFigure, select_repeats
from matplotlib.figure import Figure


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
    def test_repeat_selection_recalculates_statistics_exports_and_restores_without_source_changes(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as work, TemporaryDirectory() as destination:
            root = Path(directory)
            session(root, 'DUT1', [10, 14, 30]); session(root, 'DUT2', [20])
            before = {path: path.read_bytes() for path in root.rglob('*') if path.is_file()}
            generate_comparison(root, ['DUT1', 'DUT2'], work)
            holder = Mock(); holder.name = work
            data = ComparisonData(holder)
            original = data.get_comparison()
            excluded = {('S1', 'repeat_003')}
            selected = select_repeats(original, excluded)
            row = selected['rows'][0]
            self.assertEqual(row['values'], [10,14])
            self.assertEqual(row['mean_mA'], 12)
            self.assertAlmostEqual(row['sd_mA'], 8**.5)
            self.assertAlmostEqual(row['energy_J'], .0792)
            saved = ComparisonFigure(Figure(layout='constrained'), selected).save(destination)
            exported = json.loads((saved/'summary.json').read_text())
            self.assertEqual(exported[0]['repeat_names'], ['repeat_001','repeat_002'])
            self.assertEqual(exported[0]['omitted_repeats'], ['repeat_003'])
            csv = Path(data.export_selected_samples(destination, 0, 2, excluded))
            self.assertFalse((csv/'S1/repeat_003').exists())
            self.assertEqual(len(list(csv.rglob('samples.csv'))), 3)
            empty = select_repeats(original, {('S1', name) for name in original['rows'][0]['repeat_names']})
            self.assertEqual(empty['rows'][0]['repeats'], 0)
            self.assertIsNone(empty['rows'][0]['mean_mA'])
            self.assertIsNone(empty['rows'][0]['energy_J'])
            self.assertIsNone(empty['rows'][0]['sd_mA'])
            restored = select_repeats(original, set())
            self.assertEqual(restored['rows'][0]['values'], original['rows'][0]['values'])
            self.assertAlmostEqual(restored['rows'][0]['mean_mA'], original['rows'][0]['mean_mA'])
            self.assertAlmostEqual(restored['rows'][0]['sd_mA'], original['rows'][0]['sd_mA'])
            self.assertEqual(before, {path: path.read_bytes() for path in root.rglob('*') if path.is_file()})

    def test_selected_range_recalculates_raw_statistics_and_zoom_does_not(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as work:
            root = Path(directory)
            first = session(root, 'DUT1', [10,14])
            session(root, 'DUT2', [20,22])
            for repeat, low in [('repeat_001',10),('repeat_002',14)]:
                (first / repeat / 'samples.csv').write_text('sample_index;time_s;current_uA\n' +
                    ''.join(f'{i};{i/2};{(low if i<2 else low+20)*1000}\n' for i in range(4)))
            full = generate_comparison(root,['DUT1','DUT2'],work)
            self.assertEqual(full[0]['mean_mA'],22)
            cropped = generate_comparison(root,['DUT1','DUT2'],work,1,2)
            self.assertEqual(cropped[0]['mean_mA'],32)
            self.assertEqual(cropped[0]['seconds'],1)
            self.assertAlmostEqual(cropped[0]['sd_mA'],8**.5)
            self.assertAlmostEqual(cropped[0]['energy_J'],.1056)
            zoomed = generate_comparison(root,['DUT1','DUT2'],work,view=[1,1.5])
            self.assertEqual(zoomed[0]['mean_mA'],full[0]['mean_mA'])
            self.assertEqual(zoomed[0]['energy_J'],full[0]['energy_J'])

    def test_csv_export_keeps_timestamps_and_originals_and_close_removes_working_files(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as destination:
            root=Path(directory)
            first=session(root,'DUT1',[10])
            session(root,'DUT2',[20])
            source=first / 'repeat_001/samples.csv'
            source.write_text('sample_index;time_s;current_uA;energy_estimate_J\n0;0;10000;0.0165\n1;0.5;10000;0.033\n2;1;10000;0.0495\n3;1.5;10000;0.066\n')
            before=source.read_bytes()
            temp=TemporaryDirectory()
            generate_comparison(root,['DUT1','DUT2'],temp.name)
            view=ComparisonData(temp)
            exported=Path(view.export_selected_samples(destination,.5,1.5))
            import csv
            with (exported / 'S1/repeat_001/samples.csv').open(encoding='utf-8-sig') as file:
                rows=list(csv.DictReader(file,delimiter=';'))
            self.assertEqual([float(row['time_s']) for row in rows],[.5,1])
            self.assertEqual([int(row['sample_index']) for row in rows],[1,2])
            self.assertAlmostEqual(float(rows[0]['energy_estimate_J']),.0165)
            self.assertEqual(source.read_bytes(),before)
            self.assertFalse(list(Path(temp.name).rglob('*.csv')))
            scratch=Path(temp.name) / 'working.csv'
            scratch.write_text('temporary')
            view._close()
            self.assertFalse(Path(temp.name).exists())
            self.assertTrue(exported.exists())
            self.assertTrue(source.exists())

    def test_failed_range_keeps_previous_results_and_cleans_staging_directory(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as work:
            root=Path(directory)
            session(root,'DUT1',[10]);session(root,'DUT2',[20])
            generate_comparison(root,['DUT1','DUT2'],work)
            holder=Mock();holder.name=work
            view=ComparisonData(holder)
            original=(Path(work)/'summary.json').read_bytes()
            with self.assertRaisesRegex(RuntimeError,'Range must fit'):
                view.apply_range(0,3)
            self.assertEqual((Path(work)/'summary.json').read_bytes(),original)
            self.assertFalse(list(Path(work).glob('work_*')))

    def test_mean_sample_sd_single_repeat_exclusion_and_export(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as work, TemporaryDirectory() as destination:
            root = Path(directory)
            first = session(root, 'DUT1', [10, 14])
            session(root, 'DUT2', [20])
            invalid = first / 'repeat_invalid'
            invalid.mkdir()
            (invalid / 'metadata.json').write_text('{"status":"invalid"}')
            before = {path: path.read_bytes() for path in root.rglob('*') if path.is_file()}
            rows = generate_comparison(root, ['DUT1', 'DUT2'], work, render=True)
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
            view = ComparisonData(holder)
            plot = ComparisonFigure(Figure(layout='constrained'), view.get_comparison())
            saved = plot.save(destination)
            self.assertEqual(len(list(saved.glob('*.png'))), 2)
            self.assertEqual(len(list(saved.glob('*.svg'))), 2)
            self.assertTrue(view.get_comparison()['preview']['series'])
            session(root, 'DUT3', [30, 32])
            generate_comparison(root, ['DUT1', 'DUT3'], work, render=True)
            self.assertNotIn('SD requires at least two valid repeats.', (Path(work) / 'comparison_statistics.svg').read_text(encoding='utf-8'))

    def test_images_are_generated_only_on_save_and_hidden_sessions_are_not_drawn(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as work, TemporaryDirectory() as destination:
            root=Path(directory)
            session(root,'DUT1',[10,14]);session(root,'DUT2',[20,22])
            generate_comparison(root,['DUT1','DUT2'],work)
            self.assertFalse(list(Path(work).glob('*.png')))
            self.assertFalse(list(Path(work).glob('*.svg')))
            holder=Mock();holder.name=work
            view=ComparisonData(holder)
            data=view.apply_range(.5,1.5)
            self.assertNotIn('images',data)
            self.assertFalse(list(Path(work).glob('*.png')))
            plot=ComparisonFigure(Figure(layout='constrained'),data,['S1'])
            plot.axes[0].set_xlim(.5,1.5)
            plot.axes[1].set_ylim(19,23)
            saved=plot.save(destination)
            limits=json.loads((saved/'view.json').read_text())['limits']
            self.assertEqual(limits[0][0],[.5,1.5])
            self.assertEqual(limits[1][1],[19,23])
            rows=json.loads((saved/'summary.json').read_text())
            self.assertFalse(rows[0]['visible'])
            self.assertTrue(rows[1]['visible'])
            self.assertNotIn('S1 · DUT1',(saved/'comparison_traces.svg').read_text(encoding='utf-8'))
            self.assertEqual(len(list(saved.glob('*.png'))),2)
            self.assertEqual(len(list(saved.glob('*.svg'))),2)

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
