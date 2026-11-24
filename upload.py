"""Compile and upload a local Arduino sketch using a named board profile."""
import argparse
import os
import subprocess
import sys


PROFILES = {"nodemcu": "esp8266:esp8266:nodemcuv2:xtal=80,wipe=all,baud=115200"}


def main(argv=None):
    profiles = PROFILES
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
