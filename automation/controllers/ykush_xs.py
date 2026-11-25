"""Alternate YKUSH XS ON/OFF every five seconds during acquisition."""
import os
from pathlib import Path
import time

from automation.HIL.hubs import YkushXs
from automation.backend.hub_discovery import available_hubs, resolve_command
from src.events import emit


def main():
    stop = Path(os.environ["STLINK_STOP_FILE"])
    command = resolve_command(os.environ.get("YKUSH_CMD", "ykushcmd"))
    serial = os.environ.get("YKUSH_XS_SERIAL", "")
    if not serial:
        hubs = available_hubs("ykushxs", command)
        if len(hubs) != 1:
            raise RuntimeError("Connect exactly one YKUSH XS or set YKUSH_XS_SERIAL to its serial number")
        serial = hubs[0]["serial"]
    hub = YkushXs(command, serial, [1])

    def switch(enabled):
        hub.set(1, enabled)
        emit("hub", serial=serial, port=1, enabled=enabled)
        print(f"{time.monotonic():.3f}: YKUSH XS {serial} {'ON' if enabled else 'OFF'}", flush=True)

    hub.open()
    try:
        enabled = True
        while not stop.exists():
            switch(enabled)
            deadline = time.monotonic() + 5
            while not stop.exists() and time.monotonic() < deadline:
                time.sleep(min(.05, max(0, deadline - time.monotonic())))
            enabled = not enabled
    finally:
        try:
            switch(False)
        finally:
            hub.close()


if __name__ == "__main__":
    main()
