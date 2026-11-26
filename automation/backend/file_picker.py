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

    def pick_sketches(self):
        paths = self._window.create_file_dialog(self._webview.FileDialog.OPEN,
            allow_multiple=True, file_types=('Arduino sketch (*.ino)',))
        return [str(Path(path).resolve()) for path in paths] if paths else []

    def validate_sketches(self, paths):
        if not paths: raise ValueError('No sketches selected for active DUTs')
        for path in paths:
            if not Path(path).is_file() or Path(path).suffix.lower() != '.ino':
                raise ValueError(f'Sketch not found or not an .ino file: {path}')
