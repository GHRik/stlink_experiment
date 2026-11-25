"""Write periodic events during acquisition; no hardware required."""
import csv
import os
from pathlib import Path
import time


def main():
    directory = Path(os.environ["STLINK_RUN_DIR"])
    stop = Path(os.environ["STLINK_STOP_FILE"])
    origin = float(os.environ["STLINK_START_MONOTONIC"])
    with (directory / "controller_events.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["elapsed_s", "event"])

        def record(event):
            writer.writerow([f"{time.monotonic() - origin:.6f}", event])
            file.flush()

        record("started")
        next_event = time.monotonic()
        while not stop.exists():
            if time.monotonic() >= next_event:
                record("tick")  # Replace with your experiment action.
                next_event += 1
            time.sleep(0.02)
        record("stopped")
    print("Controller finished.")


if __name__ == "__main__":
    main()
