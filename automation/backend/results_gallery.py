"""Discover English summary plots and open their full-size versions."""
from pathlib import Path
import webbrowser
import base64
import re
from datetime import datetime


class ResultsGallery:
    def __init__(self, root=None):
        self._root = Path(root or Path(__file__).resolve().parents[2] / "results").resolve()

    def list_results(self):
        folders = set()
        for path in self._root.rglob("*_eng.*"):
            if path.stem in ("comparison_eng", "statistics_eng", "statistic_eng") and path.suffix in (".png", ".svg"):
                folders.add(path.parent)
        sessions = []
        for folder in folders:
            plots = []
            for label, stems in (("Current traces", ["comparison_eng"]),
                                 ("Summary statistics", ["statistics_eng", "statistic_eng"])):
                files = [folder / (stem + extension) for stem in stems for extension in (".png", ".svg")]
                files = [path for path in files if path.is_file()]
                if not files:
                    continue
                preview = next((path for path in files if path.suffix == ".png"), files[0])
                full = next((path for path in files if path.suffix == ".svg"), files[0])
                plots.append(dict(label=label, preview=preview.relative_to(self._root).as_posix(),
                                  path=full.relative_to(self._root).as_posix()))
            if plots:
                sessions.append(dict(name=folder.relative_to(self._root).as_posix(), plots=plots,
                                     modified=max(path.stat().st_mtime for path in folder.iterdir()
                                                  if path.name in ("comparison_eng.png", "comparison_eng.svg",
                                                                   "statistics_eng.png", "statistics_eng.svg",
                                                                   "statistic_eng.png", "statistic_eng.svg"))))
        def recorded_date(session):
            # Session names retain acquisition time even after reports are regenerated.
            for part in reversed(Path(session["name"]).parts):
                match = re.search(r"_(\d{8}_\d{6})(?:_(\d{6}))?$", part)
                if match:
                    return match[1] + "_" + (match[2] or "000000")
            return datetime.fromtimestamp(session["modified"]).strftime("%Y%m%d_%H%M%S_%f")

        sessions.sort(key=lambda session: (recorded_date(session), session["name"]), reverse=True)
        for session in sessions:
            date = recorded_date(session)
            session["date"] = f"{date[6:8]}.{date[4:6]}.{date[:4]}"
        return sessions

    def _plot(self, relative_path):
        path = (self._root / relative_path).resolve()
        if not path.is_relative_to(self._root) or path.stem not in ("comparison_eng", "statistics_eng", "statistic_eng") or path.suffix not in (".png", ".svg"):
            raise ValueError("Select a summary plot from results")
        if not path.is_file():
            raise FileNotFoundError(path)
        return path

    def result_preview(self, relative_path):
        path = self._plot(relative_path)
        mime = "image/png" if path.suffix == ".png" else "image/svg+xml"
        return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")

    def open_result(self, relative_path):
        path = self._plot(relative_path)
        return webbrowser.open(path.as_uri())
