"""Native file picker bridge checks without opening desktop windows."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

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
    @patch("automation.backend.api.DesktopApi")
    def test_demo_does_not_create_or_expose_backend(self, api):
        webview = Mock()
        run_desktop(webview, demo=True)
        api.assert_not_called()
        self.assertIsNone(webview.create_window.call_args.kwargs["js_api"])
        self.assertIn("Demo", webview.create_window.call_args.args[0])
        webview.start.assert_called_once_with()

    @patch("automation.backend.launcher.run_desktop")
    def test_demo_option_reaches_window_launcher(self, run):
        webview = Mock()
        with patch.dict("sys.modules", {"webview": webview}):
            self.assertEqual(main(["--demo"]), 0)
        run.assert_called_once_with(webview, demo=True)

    def test_window_loads_frontend_and_binds_picker(self):
        webview = Mock()
        run_desktop(webview)
        options = webview.create_window.call_args.kwargs
        self.assertEqual(Path(options["url"]),
                         Path(__file__).resolve().parents[1] / "automation/frontend/index.html")
        self.assertTrue(Path(options["url"]).is_file())
        self.assertTrue(options["maximized"])
        self.assertIs(options["js_api"]._picker._window, webview.create_window.return_value)
        webview.start.assert_called_once_with()
