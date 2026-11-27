"""Native file picker bridge checks without opening desktop windows."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from automation.backend.app import run_desktop
from automation.backend.file_picker import FilePicker
from automation.backend.launcher import main


class FilePickerTests(unittest.TestCase):
    def setUp(self):
        self.api = FilePicker(SimpleNamespace(FileDialog=SimpleNamespace(OPEN="open")))
        self.api._window = Mock()

    def test_sketch_returns_full_path(self):
        self.api._window.create_file_dialog.return_value = ("board/example.ino",)
        self.assertEqual(self.api.pick_file("sketch"), str(Path("board/example.ino").resolve()))
        self.api._window.create_file_dialog.assert_called_once_with(
            "open", allow_multiple=False, file_types=("Arduino sketch (*.ino)",))

    def test_controller_filter(self):
        self.api._window.create_file_dialog.return_value = ("controller.py",)
        self.assertEqual(self.api.pick_file("controller"), str(Path("controller.py").resolve()))
        self.assertEqual(self.api._window.create_file_dialog.call_args.kwargs["file_types"],
                         ("Python script (*.py)",))

    def test_cancel_returns_none(self):
        self.api._window.create_file_dialog.return_value = None
        self.assertIsNone(self.api.pick_file("sketch"))

    def test_unknown_picker_is_rejected(self):
        with self.assertRaises(ValueError):
            self.api.pick_file("other")
        self.api._window.create_file_dialog.assert_not_called()


class DesktopAppTests(unittest.TestCase):
    @patch('automation.backend.app.ctypes')
    @patch('automation.backend.api.DesktopApi')
    def test_windows_taskbar_groups_real_and_demo_separately(self, api, native):
        with patch('automation.backend.app.sys.platform', 'win32'):
            run_desktop(MagicMock(), demo=False)
            run_desktop(MagicMock(), demo=True)
        self.assertEqual([call.args[0] for call in native.windll.shell32.SetCurrentProcessExplicitAppUserModelID.call_args_list],
                         ['GHRik.STLINK.PowerMeasurements', 'GHRik.STLINK.PowerMeasurements.Demo'])

    @patch("automation.backend.api.DesktopApi")
    def test_demo_exposes_only_temporary_results_without_hardware(self, api):
        webview = MagicMock()
        run_desktop(webview, demo=True)
        api.assert_not_called()
        demo = webview.create_window.call_args.kwargs['js_api']
        self.assertTrue(callable(demo.compare_results))
        self.assertFalse(any(hasattr(demo, name) for name in ('list_ports','start_capture','start_upload','set_meter_power','set_hub_port','set_relay')))
        self.assertFalse(demo._root.exists())
        self.assertIn("Demo", webview.create_window.call_args.args[0])
        self.assertEqual(Path(webview.start.call_args.kwargs['icon']).name, 'stlink-demo.ico')
        self.assertTrue(Path(webview.start.call_args.kwargs['icon']).is_file())

    @patch("automation.backend.launcher.run_desktop")
    def test_demo_option_reaches_window_launcher(self, run):
        webview = Mock()
        with patch.dict("sys.modules", {"webview": webview}):
            self.assertEqual(main(["--demo"]), 0)
        run.assert_called_once_with(webview, demo=True)

    def test_window_loads_frontend_and_binds_picker(self):
        webview = MagicMock()
        run_desktop(webview)
        options = webview.create_window.call_args.kwargs
        self.assertEqual(Path(options["url"]),
                         Path(__file__).resolve().parents[1] / "automation/frontend/index.html")
        self.assertTrue(Path(options["url"]).is_file())
        self.assertTrue(options["maximized"])
        self.assertIs(options["js_api"]._picker._window, webview.create_window.return_value)
        self.assertEqual(Path(webview.start.call_args.kwargs['icon']).name, 'stlink.ico')
        self.assertTrue(Path(webview.start.call_args.kwargs['icon']).is_file())
