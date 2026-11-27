"""Run the measurement CLI with a cooperative GUI STOP request."""
import _thread
import os
from pathlib import Path
import sys
from threading import Event, Thread

from src.stlink_measure import main as measure_main


def main(entrypoint=None):
    finished = Event()
    stop_file = Path(os.environ["STLINK_GUI_STOP_FILE"])

    def watch_stop():
        while not finished.wait(0.1):
            if stop_file.exists():
                _thread.interrupt_main()
                return

    watcher = Thread(target=watch_stop, daemon=True, name="stlink-stop-watcher")
    watcher.start()
    try:
        return (entrypoint or measure_main)()
    except KeyboardInterrupt:
        return 130
    finally:
        finished.set()
        watcher.join(timeout=1)


if __name__ == "__main__":
    sys.exit(main())
