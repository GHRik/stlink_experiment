"""Create the desktop window and connect its Python bridge."""
from pathlib import Path

from .file_picker import FilePicker


def run_desktop(webview):
    api = FilePicker(webview)
    api._window = webview.create_window(
        "STLINK power measurements",
        url=str(Path(__file__).resolve().parents[1] / "frontend" / "index.html"),
        js_api=api,
        width=1440,
        height=960,
        min_size=(900, 600),
    )
    webview.start()
