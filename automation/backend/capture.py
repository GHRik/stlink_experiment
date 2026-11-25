"""Launch the existing capture CLI and stream its output to the desktop UI."""
from collections import deque
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Lock, Thread


def capture_command(config):
    notes = config.get("description", "")
    command = [sys.executable, "-u", "-m", "automation.backend.capture_worker", "capture",
               "--port", config["port"], "--name", config["name"].strip(), "--notes", notes]
    flags = {"repeats": "--repeats", "seconds": "--seconds", "hz": "--hz",
             "voltage": "--voltage", "warmup_seconds": "--warmup-seconds", "off_seconds": "--off-seconds"}
    for key, flag in flags.items():
        if key in config:
            command.extend([flag, str(config[key])])
    if config.get("controller"):
        command.extend(["--controller", config["controller"]])
    return command


class CaptureProcess:
    def __init__(self, directory=None):
        self._directory = Path(directory) if directory else Path(__file__).resolve().parents[2]
        self._lock = Lock()
        self._process = None
        self._thread = None
        self._running = False
        self._stopping = False
        self._returncode = None
        self._lines = deque(maxlen=2000)
        self._sequence = 0
        self._stop_file = None

    def start(self, config):
        command = capture_command(config)
        with self._lock:
            if self._running:
                raise RuntimeError("A capture is already running")
            self._lines.clear()
            self._sequence = 0
            self._returncode = None
            self._stopping = False
            stop_directory = TemporaryDirectory(prefix="stlink_gui_")
            self._stop_file = Path(stop_directory.name) / "stop"
            try:
                self._process = subprocess.Popen(
                    command, cwd=self._directory, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1",
                             STLINK_GUI_STOP_FILE=str(self._stop_file)),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except BaseException:
                stop_directory.cleanup()
                raise
            self._running = True
            self._thread = Thread(target=self._read_output, args=(self._process, stop_directory), daemon=True)
            self._thread.start()
        return {"command": command, "directory": str(self._directory)}

    def _read_output(self, process, stop_directory):
        try:
            for line in process.stdout:
                with self._lock:
                    self._sequence += 1
                    self._lines.append((self._sequence, line.rstrip("\r\n")))
        finally:
            process.stdout.close()
            code = process.wait()
            with self._lock:
                self._returncode = code
                self._running = False
                stop_directory.cleanup()

    def status(self, after=0):
        with self._lock:
            return {"running": self._running, "stopping": self._stopping,
                    "returncode": self._returncode, "cursor": self._sequence,
                    "lines": [line for sequence, line in self._lines if sequence > after]}

    def stop(self):
        with self._lock:
            process = self._process
            if not self._running or process is None or self._stopping:
                return
            self._stopping = True
            self._stop_file.touch()

    def close(self):
        self.stop()
        if self._thread is not None:
            self._thread.join(timeout=20)
        return not self.status()["running"]
