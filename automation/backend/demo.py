"""Temporary synthetic results and the existing comparer; no hardware methods."""
from datetime import datetime
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from threading import RLock
from urllib.parse import unquote

from .comparison import ComparisonService
from .results_gallery import ResultsGallery
from src.storage import write_csv


class DemoApi:
    def __init__(self, webview):
        self._directory = TemporaryDirectory(prefix='stlink_demo_')
        self._root = Path(self._directory.name)
        self._gallery = ResultsGallery(self._root)
        self._comparisons = ComparisonService(webview, self._root)
        self._lock, self._closed = RLock(), False

    def _bind_window(self, window):
        pass

    def save_demo_result(self, name, traces, config, plots):
        import numpy as np
        with self._lock:
            if self._closed: raise RuntimeError('Demo is closed')
            label = 'DEMO_' + re.sub(r'[^A-Za-z0-9_-]', '_', name)[:80]
            folder = self._root / (label + '_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
            folder.mkdir()
            seconds, voltage = float(config['seconds']), float(config['voltage'])
            for index, trace in enumerate(traces, 1):
                points = np.asarray(trace, dtype=float)
                count = max(2, len(points)-1)
                hz = count / seconds
                times = np.arange(count)/hz
                current = np.interp(times, points[:,0], points[:,1])*1000
                repeat = folder/f'repeat_{index:03d}'; repeat.mkdir()
                write_csv(repeat/'samples.csv', [dict(sample_index=i,time_s=float(t),current_uA=float(c))
                          for i,(t,c) in enumerate(zip(times,current))])
                (repeat/'metadata.json').write_text(json.dumps(dict(status='valid', synthetic=True,
                    configuration=label, voltage_V=voltage, sampling_Hz=hz, samples=count,
                    requested_duration_s=seconds, board_notes='Synthetic demo data; not a hardware measurement.',
                    identity=dict(demo=True))), encoding='utf-8')
            for stem, source in zip(('comparison_eng','statistics_eng'), plots):
                if not source.startswith('data:image/svg+xml;charset=utf-8,'):
                    raise ValueError('Expected a synthetic SVG preview')
                (folder/f'{stem}.svg').write_text(unquote(source.partition(',')[2]), encoding='utf-8')
            return folder.name

    def list_results(self):
        with self._lock:
            return [] if self._closed else self._gallery.list_results()

    def result_preview(self, path):
        with self._lock: return self._gallery.result_preview(path)

    def open_result(self, path):
        with self._lock: return self._gallery.open_result(path)

    def compare_results(self, sessions):
        with self._lock:
            if self._closed: raise RuntimeError('Demo is closed')
            return self._comparisons.open(sessions)

    def _on_closing(self):
        with self._lock:
            if self._closed: return True
            self._closed = True
        self._comparisons.close()
        self._directory.cleanup()
        return True
