"""Demo results use only disposable files and the normal comparison implementation."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from automation.backend.demo import DemoApi
from automation.backend.comparison import generate_comparison

SVG='data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3C%2Fsvg%3E'


class DemoResultTests(unittest.TestCase):
    def test_demo_sessions_are_comparable_and_removed_when_owner_closes(self):
        api=DemoApi(Mock());root=api._root
        try:
            def save(name,means):
                return api.save_demo_result(name,[[[0,mean,mean,mean],[.5,mean,mean,mean],[1,mean,mean,mean]]
                    for mean in means],dict(seconds=1,voltage=3.3),[SVG,SVG])
            first=save('idle',[10,14]);second=save('sleep',[1,2]);save('new_run',[20])
            sessions=api.list_results()
            self.assertEqual(len(sessions),3)
            self.assertTrue(all(session['name'].startswith('DEMO_') for session in sessions))
            self.assertTrue(api.result_preview(sessions[0]['plots'][0]['preview']).startswith('data:image/svg+xml;base64,'))
            self.assertTrue((root/first/'repeat_001/samples.csv').is_file())
            with TemporaryDirectory() as output:
                rows=generate_comparison(root,[first,second],output)
                self.assertEqual(rows[0]['mean_mA'],12)
                self.assertAlmostEqual(rows[0]['sd_mA'],8**.5)
                self.assertAlmostEqual(rows[0]['energy_J'],.0396)
            api._comparisons=Mock()
            api.compare_results([first,second])
            api._comparisons.open.assert_called_once_with([first,second])
            api._on_closing()
            api._comparisons.close.assert_called_once()
            self.assertFalse(root.exists())
            self.assertEqual(api.list_results(),[])
            with self.assertRaisesRegex(RuntimeError,'closed'):save('late',[1])
        finally:api._on_closing()

    def test_demo_does_not_expose_hardware_and_gallery_cannot_read_outside_tmp(self):
        api=DemoApi(Mock())
        try:
            self.assertFalse(any(hasattr(api,name) for name in ('list_ports','start_capture','start_hil','set_hub_port','set_relay')))
            with self.assertRaises(ValueError):api.result_preview('../comparison_eng.svg')
        finally:api._on_closing()
