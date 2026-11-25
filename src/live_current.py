"""Bounded-rate preview bins; full-resolution recording remains in the capture loop."""
import os
from .events import emit


class LiveCurrentPreview:
    def __init__(self, name, repeat, hz):
        self.enabled = bool(os.environ.get("STLINK_GUI_EVENT_FILE"))
        self.name, self.repeat, self.hz = name, repeat, hz
        self.bin_samples = max(1, round(hz * .05))
        self.batch_bins = max(1, round(hz * .5 / self.bin_samples))
        self.points = []
        self.count = 0
        self.total = 0.0

    def add(self, value, index):
        if not self.enabled:
            return
        current = value * 1000  # A -> mA
        if not self.count:
            self.first = index
            self.minimum = self.maximum = current
        self.last = index
        self.count += 1
        self.total += current
        self.minimum = min(self.minimum, current)
        self.maximum = max(self.maximum, current)
        if self.count >= self.bin_samples:
            self._finish_bin()
        if len(self.points) >= self.batch_bins:
            self.flush()

    def _finish_bin(self):
        if self.count:
            self.points.append([(self.first + self.last) / (2 * self.hz),
                                self.total / self.count, self.minimum, self.maximum])
            self.count = 0
            self.total = 0.0

    def flush(self):
        self._finish_bin()
        if self.points:
            emit("current_samples", name=self.name, repeat=self.repeat, points=self.points)
            self.points = []
