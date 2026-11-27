"""Optional GUI telemetry shared by the runner and its measurement subprocesses."""
import json
import os
import time
from pathlib import Path


def check_stop():
    path = os.environ.get("STLINK_GUI_STOP_FILE")
    if path and Path(path).exists():
        raise KeyboardInterrupt


def emit(kind, **details):
    path = os.environ.get("STLINK_GUI_EVENT_FILE")
    if not path:
        return
    data = (json.dumps(dict(type=kind, time=time.time(), **details)) + "\n").encode("utf-8")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(descriptor, data)
        finally:
            os.close(descriptor)
    except OSError:
        # Losing a GUI update must not interrupt measurement or hardware cleanup.
        pass
