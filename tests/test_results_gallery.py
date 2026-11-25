"""Summary-plot discovery for both standalone and nested HIL sessions."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from automation.backend.results_gallery import ResultsGallery


class ResultsGalleryTests(unittest.TestCase):
    def test_sorts_by_session_date_descending_even_after_old_plots_are_regenerated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ['old_20261115_205305_543823',
                     'automation_20261117_180000_000000/measurements/board',
                     'new_20261125_185152_382343']
            for name in names:
                folder = root / name
                folder.mkdir(parents=True)
                plot = folder / 'comparison_eng.png'
                plot.touch()
                os.utime(plot, (2000000000, 2000000000))
            rows = ResultsGallery(root).list_results()
            self.assertEqual([row['name'] for row in rows], list(reversed(names)))
            self.assertEqual([row['date'] for row in rows], ['25.11.2026', '17.11.2026', '15.11.2026'])

    def test_discovers_sessions_and_prefers_png_previews_with_svg_full_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = root / 'automation_1' / 'measurements' / 'board_relay1'
            session.mkdir(parents=True)
            for name in ('comparison_eng.png', 'comparison_eng.svg', 'statistics_eng.png',
                         'statistics_eng.svg', 'comparison_pl.png', 'current.png'):
                (session / name).touch()
            gallery = ResultsGallery(root)
            rows = gallery.list_results()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['name'], 'automation_1/measurements/board_relay1')
            self.assertEqual(len(rows[0]['plots']), 2)
            plot = rows[0]['plots'][0]
            self.assertIn('comparison_eng.png', plot['preview'])
            self.assertTrue(gallery.result_preview(plot['preview']).startswith('data:image/png;base64,'))
            self.assertTrue(plot['path'].endswith('comparison_eng.svg'))
            with patch('automation.backend.results_gallery.webbrowser.open') as open_plot:
                gallery.open_result(plot['path'])
            open_plot.assert_called_once_with((session / 'comparison_eng.svg').as_uri())

    def test_handles_partial_results_svg_only_and_singular_statistics_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'comparison_eng.svg').touch()
            (root / 'statistic_eng.png').touch()
            rows = ResultsGallery(root).list_results()
            self.assertEqual(len(rows[0]['plots']), 2)
            self.assertTrue(rows[0]['plots'][0]['path'].endswith('.svg'))
            self.assertIn('statistic_eng.png', rows[0]['plots'][1]['preview'])

    def test_empty_results_and_opening_outside_results(self):
        with tempfile.TemporaryDirectory() as directory:
            gallery = ResultsGallery(directory)
            self.assertEqual(gallery.list_results(), [])
            with self.assertRaises(ValueError):
                gallery.open_result('../comparison_eng.svg')
