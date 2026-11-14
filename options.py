"""Opcje terminala. Przebieg eksperymentu jest w stlink_measure.py."""
import argparse

RATES = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000)


def read_options():
    parser = argparse.ArgumentParser(description="Pomiary STLINK-V3PWR, CSV i wykresy")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("ports", help="Lista portow; wybierz STLINK SMU, nie UART debug.")
    capture = sub.add_parser("capture", help="Automatyczna seria pomiarow.")
    capture.add_argument("--port", required=True)
    capture.add_argument("--name", required=True)
    capture.add_argument("--repeats", type=int, default=10)
    capture.add_argument("--seconds", type=float, default=120)
    capture.add_argument("--hz", type=int, choices=RATES, default=1000)
    capture.add_argument("--voltage", type=float, default=3.3)
    capture.add_argument("--off-seconds", type=float, default=1)
    capture.add_argument("--out", default="results")
    capture.add_argument("--notes", default="NodeMCU V3; CPU 80 MHz; LED_BUILTIN; USB disconnected")
    analysis = sub.add_parser("analyze", help="Ponowna analiza CSV, bez polaczenia z urzadzeniem.")
    analysis.add_argument("--root", default="results")
    analysis.add_argument("--from-s", type=float, default=0)
    analysis.add_argument("--to-s", type=float)
    simulation = sub.add_parser("demo", help="Wygeneruj wyraznie oznaczone dane syntetyczne.")
    simulation.add_argument("--out", default="demo_results")
    return parser.parse_args()

