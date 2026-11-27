"""Compile and upload a local Arduino sketch using a named board profile."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
from tempfile import TemporaryDirectory


def default_arduino_cli():
    if os.environ.get("ARDUINO_CLI"):
        return os.environ["ARDUINO_CLI"]
    executable = shutil.which("arduino-cli")
    if executable:
        return executable
    # Arduino IDE bundles the CLI without adding it to PATH on Windows.
    for variable, directory in (("LOCALAPPDATA", "Programs/Arduino IDE"),
                                ("ProgramFiles", "Arduino IDE"),
                                ("ProgramFiles(x86)", "Arduino IDE")):
        if os.environ.get(variable):
            path = Path(os.environ[variable]) / directory / "resources/app/lib/backend/resources/arduino-cli.exe"
            if path.is_file():
                return str(path)
    return "arduino-cli"


def load_profiles():
    path = Path(__file__).resolve().parents[1] / 'HIL/board_profiles.json'
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main(argv=None):
    profiles = load_profiles()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("board", choices=profiles, help="Board configuration profile")
    parser.add_argument("port", help="Board upload port, e.g. COM22 (not STLINK)")
    parser.add_argument("sketch", help="Local .ino file or sketch directory")
    parser.add_argument("--cli", default=default_arduino_cli(),
                        help="Arduino CLI executable; default: ARDUINO_CLI, PATH or Arduino IDE bundle")
    args = parser.parse_args(argv)
    # Keep compilation and upload exit codes separate; inherit Arduino CLI diagnostics.
    with TemporaryDirectory(prefix="arduino_upload_") as build:
        result = subprocess.run([args.cli, "compile", "--verbose", "--fqbn", profiles[args.board],
                                 "--build-path", build, args.sketch])
        if result.returncode:
            return result.returncode
        return subprocess.run([args.cli, "upload", "--verbose", "--fqbn", profiles[args.board],
                               "--port", args.port, "--input-dir", build, args.sketch]).returncode


if __name__ == "__main__":
    sys.exit(main())
