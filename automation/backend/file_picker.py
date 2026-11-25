"""Native file selection exposed to the trusted local frontend."""
from pathlib import Path


class FilePicker:
    """Return local sketch and controller paths through the webview bridge."""

    def __init__(self, webview):
        self._webview = webview
        self._window = None

    def pick_file(self, kind):
        filters = {"sketch": "Arduino sketch (*.ino)", "controller": "Python script (*.py)"}
        if kind not in filters:
            raise ValueError("Expected sketch or controller")
        paths = self._window.create_file_dialog(
            self._webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=(filters[kind],),
        )
        return str(Path(paths[0]).resolve()) if paths else None
