#!/usr/bin/env python3
"""Eksperyment z NodeMCU: start zasilania -> pomiar -> pliki -> porownanie.

Przyklad:
    py stlink_measure.py capture --port COM18 --name modem --repeats 10

Domyslnie: 3.3 V, 1000 Hz, 120 s na pomiar, 10 powtorzen.
Wgraj odpowiedni program NodeMCU przed uruchomieniem skryptu.
"""
from pathlib import Path
import sys

from options import read_options
from results import analyze_run, report, demo
from storage import save_json
from stlink_protocol import (
    Device, validate_settings, create_session, identify_device,
    configure_device, save_session_settings, capture_one,
)


def run_experiment(settings):
    """Calosc czytana od gory: przygotuj, zmierz, zamknij, podsumuj."""
    validate_settings(settings)
    session = create_session(settings)
    meter = Device(settings.port)

    try:
        identity = identify_device(meter)
        configure_device(meter, settings)
        save_session_settings(session, meter, settings, identity)

        for number in range(1, settings.repeats + 1):
            print(f"Pomiar {number}/{settings.repeats}: {settings.name}", flush=True)
            run_folder = session / f"run_{number:03d}"

            # Odetnij zasilanie, zacznij od nowa i zapisz wszystkie probki.
            capture_one(meter, run_folder, settings, identity, number)

            # Policz wynik i narysuj przebieg tego jednego pomiaru.
            analyze_run(run_folder, begin=0, end=None)

    finally:
        # Rowniez po bledzie lub Ctrl+C: zachowaj log i probuj wylaczyc OUT.
        save_json(session / "last_commands.json", meter.events)
        meter.close()

    # Po serii porownaj zebrane konfiguracje i policz rozrzut powtorzen.
    report(Path(settings.out), begin=0, end=None)
    print(f"Zapisano: {session.resolve()}")


def analyze_saved_measurements(settings):
    """Ponowna analiza wybranego czasu, bez wlaczania miernika."""
    report(Path(settings.root), begin=settings.from_s, end=settings.to_s)


def show_ports():
    """Pokaz porty, aby mozna bylo wybrac pomiarowy port SMU."""
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
        print("Przerwano. Niepelne pomiary sa oznaczone invalid.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"BLAD: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
