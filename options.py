"""Opcje terminala. Przebieg eksperymentu jest w stlink_measure.py."""
import argparse

RATES = (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000)

REQUIRED_REASONS = {
    "--name": "Required to identify the tested configuration and name its results directory; date and time are appended automatically.",
    "--notes": "Required to document the board, firmware, and measurement conditions so results can be interpreted and reproduced. These details cannot be inferred from the meter.",
}


class MeasurementParser(argparse.ArgumentParser):
    def error(self, message):
        reasons = [reason for option, reason in REQUIRED_REASONS.items() if option in message]
        super().error("\n".join([message, *reasons]))


def nonempty_text(value):
    if not value.strip():
        raise argparse.ArgumentTypeError("must not be empty or whitespace")
    return value.strip()


def read_options():
    parser = MeasurementParser(description="STLINK-V3PWR measurements, CSV exports, and plots")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("ports", help="Lista portow; wybierz STLINK SMU, nie UART debug.")
    capture = sub.add_parser("capture", help="Automatyczna seria pomiarow.")
    capture.add_argument("--port", required=True)
    capture.add_argument("--name", required=True, type=nonempty_text,
                         help=REQUIRED_REASONS["--name"])
    capture.add_argument("--repeats", type=int, default=10)
    capture.add_argument("--seconds", type=float, default=120)
    capture.add_argument("--hz", type=int, choices=RATES, default=1000)
    capture.add_argument("--voltage", type=float, default=3.3)
    capture.add_argument("--off-seconds", type=float, default=1)
    capture.add_argument("--out", default="results")
    capture.add_argument("--notes", required=True, type=nonempty_text,
                         help=REQUIRED_REASONS["--notes"])
    analysis = sub.add_parser("analyze", help="Ponowna analiza CSV, bez polaczenia z urzadzeniem.")
    analysis.add_argument("--root", default="results")
    analysis.add_argument("--from-s", type=float, default=0)
    analysis.add_argument("--to-s", type=float)
    simulation = sub.add_parser("demo", help="Wygeneruj wyraznie oznaczone dane syntetyczne.")
    simulation.add_argument("--out", default="demo_results")
    return parser.parse_args()

