#!/usr/bin/env python3
"""NodeMCU experiment: power-on -> acquisition -> saved data -> comparison.

Example:
    py -m src.stlink_measure capture --port COM18 --name modem --notes "NodeMCU; test firmware" --repeats 10

Defaults: 3.3 V, 1000 Hz, 100 s per capture, 10 repeats.
Upload the appropriate NodeMCU firmware before running this script.
"""
from pathlib import Path
import sys

from .options import read_options
from .results import analyze_run, report, demo
from .storage import save_json
from .stlink_protocol import (
    Device, validate_settings, create_session, identify_device,
    configure_device, save_session_settings, capture_one, warm_up,
)


def run_experiment(settings):
    """Prepare the meter, capture repeats, close the device, and summarize results."""
    validate_settings(settings)
    session = create_session(settings)
    meter = Device(settings.port)

    try:
        identity = identify_device(meter)
        configure_device(meter, settings)
        save_session_settings(session, meter, settings, identity)
        save_json(session / "warmup.json", warm_up(meter, getattr(settings, "warmup_seconds", 180)))

        for number in range(1, settings.repeats + 1):
            print(f"Repeat {number}/{settings.repeats}: {settings.name}", flush=True)
            run_folder = session / f"repeat_{number:03d}"

            # Power-cycle the target and record all samples for this repeat.
            capture_one(meter, run_folder, settings, identity, number)

            # Analyze and plot this repeat.
            analyze_run(run_folder, begin=0, end=None)

    finally:
        # Preserve the log and attempt to disable OUT, including after errors or Ctrl+C.
        try:
            save_json(session / "last_commands.json", meter.events)
        finally:
            meter.close()

    # Generate comparison plots and statistics across repeats.
    report(session, begin=0, end=None)
    print(f"Saved to: {session.resolve()}")


def analyze_saved_measurements(settings):
    """Reanalyze the selected time window without connecting to the meter."""
    report(Path(settings.root), begin=settings.from_s, end=settings.to_s)


def show_ports():
    """List serial ports so the measurement SMU port can be selected."""
    from serial.tools import list_ports
    for port in list_ports.comports():
        print(f"{port.device}: {port.description} | {port.hwid}")


def main():
    settings = read_options()
    try:
        if settings.action == "capture":
            run_experiment(settings)
        elif settings.action == "analyze":
            analyze_saved_measurements(settings)
        elif settings.action == "ports":
            show_ports()
        elif settings.action == "demo":
            demo(settings.out)
    except KeyboardInterrupt:
        print("Interrupted. Incomplete measurements are marked invalid.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
