"""Compile and upload a local Arduino sketch using a named board profile."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def load_profiles():
    path = Path(__file__).with_name("board_profiles.json")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main(argv=None):
    profiles = load_profiles()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("board", choices=profiles, help="Board configuration profile")
    parser.add_argument("port", help="Board upload port, e.g. COM22 (not STLINK)")
    parser.add_argument("sketch", help="Local .ino file or sketch directory")
    parser.add_argument("--cli", default=os.environ.get("ARDUINO_CLI", "arduino-cli"),
                        help="Arduino CLI executable; default: ARDUINO_CLI or PATH")
    args = parser.parse_args(argv)
    # Inherit stdout/stderr: compiler and uploader diagnostics come directly from CLI.
    return subprocess.run([args.cli, "compile", "--upload", "--verbose",
                           "--fqbn", profiles[args.board], "--port", args.port,
                           args.sketch]).returncode


if __name__ == "__main__":
    sys.exit(main())
