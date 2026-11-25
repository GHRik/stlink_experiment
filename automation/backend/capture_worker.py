"""Run the measurement CLI with a cooperative GUI STOP request."""
import _thread
import os
from pathlib import Path
import sys
from threading import Event, Thread

from src.stlink_measure import main as measure_main


def main():
    finished = Event()
    stop_file = Path(os.environ["STLINK_GUI_STOP_FILE"])

    def watch_stop():
        while not finished.wait(0.1):
            if stop_file.exists():
                _thread.interrupt_main()
                return

    Thread(target=watch_stop, daemon=True).start()
    try:
        return measure_main()
    except KeyboardInterrupt:
        return 130
    finally:
        finished.set()


if __name__ == "__main__":
    sys.exit(main())
