"""Run an optional user script alongside one acquisition."""
import os
from pathlib import Path
import subprocess
import sys
import time
import signal


class MeasurementController:
    def __init__(self, script, directory, seconds):
        self.script = Path(script).resolve()
        self.directory = Path(directory).resolve()
        self.seconds = seconds
        self.stop_file = self.directory / "controller.stop"
        self.process = None
        self.log = None
        self.started = None
        self.outcome = None

    def start(self):
        self.stop_file.unlink(missing_ok=True)
        self.outcome = None
        self.started = time.monotonic()
        env = dict(os.environ, STLINK_RUN_DIR=str(self.directory),
                   STLINK_DURATION_S=str(self.seconds), STLINK_STOP_FILE=str(self.stop_file),
                   STLINK_START_MONOTONIC=str(self.started))
        self.log = (self.directory / "controller.log").open("wb")
        try:
            self.process = subprocess.Popen([sys.executable, "-u", str(self.script)],
                                            env=env, stdin=subprocess.DEVNULL,
                                            stdout=self.log, stderr=subprocess.STDOUT,
                                            start_new_session=os.name != 'nt',
                                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except BaseException:
            self.log.close()
            raise

    def check(self):
        code = self.process.poll()
        if code is not None and code != 0:
            raise RuntimeError(f"Controller exited with code {code}; see controller.log")

    def request_stop(self):
        if self.process is not None:
            self.stop_file.touch()

    def close(self):
        if self.outcome is not None:
            return self.outcome
        if self.process is None:
            return None
        forced = False
        try:
            self.request_stop()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                forced = True
                if os.name == "nt":
                    # A venv launcher can own a child interpreter that still holds the log.
                    result = subprocess.run(
                        ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                    if result.returncode and self.process.poll() is None:
                        raise RuntimeError("Could not terminate the controller process tree")
                else:
                    os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=10)
            self.outcome = {"script": str(self.script), "start_monotonic": self.started,
                            "returncode": self.process.returncode, "forced_stop": forced}
            return self.outcome
        finally:
            self.log.close()
