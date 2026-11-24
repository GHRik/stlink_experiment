"""Sequential firmware upload and STLINK measurement through YKUSH and Numato."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_config(path):
    path = Path(path).resolve()
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if "ykush" in config:
        # Keep the execution layer independent of the human-facing config layout.
        config = {
            "ykush_cmd": config["ykush"]["cmd"],
            "ykush_serial": config["ykush"]["serial"],
            "ykush_model_argument": config["ykush"]["model_argument"],
            "ykush_ports": config["ykush"]["ports"],
            "numato_controller_port": config["numato"]["controller_port"],
            "numato_ports": config["numato"]["ports"],
            "numato_channel_digits": config["numato"]["channel_digits"],
            "stlink_com": config["stlink"]["com"],
            "measurement": config["stlink"]["measurement"],
            "arduino_cli": config["upload"]["arduino_cli"],
            "sketch": config["upload"]["sketch"],
            "flash_timeout_s": config["upload"]["timeout_s"],
            "step_delay_s": config["timing"]["step_delay_s"],
            "port_timeout_s": config["timing"]["port_timeout_s"],
            "connected_boards": config["connected_boards"],
        }
    config["sketch"] = str((path.parent / config["sketch"]).resolve())
    boards = config["connected_boards"]
    if not isinstance(boards, list) or not 1 <= len(boards) <= 3:
        raise ValueError("connected_boards must contain 1 to 3 board mappings")
    count = config["numato_ports"]
    if type(count) is not int or not 1 <= count <= 64:
        raise ValueError("numato_ports must be the relay count (1 to 64)")
    ports = config["ykush_ports"]
    if not ports or any(type(p) is not int or p not in (1, 2, 3) for p in ports) or len(set(ports)) != len(ports):
        raise ValueError("ykush_ports must be unique USB port numbers from 1 to 3")
    for field in ("name", "usb_port", "com", "relay"):
        values = [board[field] for board in boards]
        if len(set(str(v).upper() for v in values)) != len(values):
            raise ValueError(f"Board {field} values must be unique")
    device_ports = [config["stlink_com"], config["numato_controller_port"], *[b["com"] for b in boards]]
    if any(not isinstance(p, str) or not p.strip() for p in device_ports) or len(set(p.upper() for p in device_ports)) != len(device_ports):
        raise ValueError("STLINK, Numato and board COM ports must be distinct and nonempty")
    for board in boards:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", board["name"]) or not board["notes"].strip():
            raise ValueError("Each board needs an ASCII name and nonempty measurement notes")
        if type(board["usb_port"]) is not int or board["usb_port"] not in ports:
            raise ValueError("Board USB port is not in ykush_ports")
        if type(board["relay"]) is not int or not 0 <= board["relay"] < count:
            raise ValueError("Board relay must be a zero-based Numato channel")
    from upload import load_profiles
    profiles = load_profiles()
    for board in boards:
        if board.get("upload_profile") not in profiles:
            raise ValueError(f"Board {board['name']}: upload_profile must match a profile in board_profiles.json")
    for field in ("step_delay_s", "port_timeout_s", "flash_timeout_s"):
        if not math.isfinite(config[field]) or config[field] <= 0:
            raise ValueError(f"{field} must be positive and finite")
    if config["numato_channel_digits"] not in (1, 2, 3):
        raise ValueError("numato_channel_digits must be 1, 2 or 3")
    if not config["ykush_serial"].strip():
        raise ValueError("ykush_serial is required")
    if config["ykush_model_argument"] not in ("", "ykush", "ykush3"):
        raise ValueError("Use an empty model argument for legacy CLI, or ykush / ykush3")
    # Use the existing measurement validator before switching any hardware.
    from stlink_protocol import validate_settings
    m = config["measurement"]
    for board in boards:
        validate_settings(argparse.Namespace(name=board["name"], repeats=m["repeats"],
                          seconds=m["seconds"], hz=m["hz"], voltage=m["voltage"],
                          off_seconds=m["off_seconds"], warmup_seconds=m["warmup_seconds"]))
    if type(m["repeats"]) is not int or m["hz"] not in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000):
        raise ValueError("Invalid repeat count or sampling frequency")
    return config


def run_command(command, timeout, log=None):
    """Terminate the process tree on timeout or interruption before disconnecting power."""
    process = subprocess.Popen(command, stdout=log or subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True,
                               start_new_session=os.name != "nt")
    try:
        output, _ = process.communicate(timeout=timeout)
    except BaseException:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
        raise
    if process.returncode:
        raise RuntimeError(f"Command failed ({process.returncode}): {command!r}\n{output or 'See operation log.'}")
    return output or ""


class Hardware:
    def __init__(self, config, directory):
        self.config = config
        self.directory = directory
        self.serial = None

    def event(self, action, **details):
        print(action, details or "", flush=True)
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),
                                       monotonic_s=time.monotonic(), action=action, **details)) + "\n")

    def pause(self):
        time.sleep(self.config["step_delay_s"])

    def open(self):
        import serial
        self.serial = serial.Serial(self.config["numato_controller_port"], 19200,
                                    timeout=2, write_timeout=3)

    def command(self, text):
        self.serial.reset_input_buffer()
        self.serial.write((text + "\r").encode("ascii"))
        self.serial.flush()
        response = self.serial.read_until(b">").decode("ascii", errors="replace")
        self.event("numato", command=text, response=response)
        if not response.endswith(">") or re.search(r"error|invalid|unknown", response, re.I):
            raise RuntimeError(f"Numato command failed: {text!r}: {response!r}")
        return response

    def relay(self, channel, enabled):
        state = "on" if enabled else "off"
        index = f"{channel:0{self.config['numato_channel_digits']}d}"
        self.command(f"relay {state} {index}")
        response = self.command(f"relay read {index}")
        states = re.findall(r"(?im)^\s*(on|off)\s*$", response.replace(">", ""))
        if not states or states[-1].lower() != state:
            raise RuntimeError(f"Numato relay {channel} did not confirm {state}")

    def usb(self, port, enabled):
        c = self.config
        base = [c["ykush_cmd"]]
        if c["ykush_model_argument"]:
            base.append(c["ykush_model_argument"])
        base += ["-s", c["ykush_serial"]]
        response = run_command(base + ["-u" if enabled else "-d", str(port)], 15)
        status = run_command(base + ["-g", str(port)], 15)
        self.event("ykush", port=port, enabled=enabled, response=response, status=status)
        if not re.search(r"\b" + ("ON" if enabled else "OFF") + r"\b", status, re.I):
            raise RuntimeError(f"YKUSH port {port} state not confirmed: {status}")

    def wait_port(self, port):
        from serial.tools.list_ports import comports
        deadline = time.monotonic() + self.config["port_timeout_s"]
        while time.monotonic() < deadline:
            if port.upper() in {p.device.upper() for p in comports()}:
                return
            time.sleep(.2)
        raise RuntimeError(f"Board upload port did not appear: {port}")

    def flash(self, board):
        self.event("flash", board=board["name"], port=board["com"])
        with (self.directory / f"{board['name']}_upload.log").open("w", encoding="utf-8") as log:
            run_command([sys.executable, "-u", str(ROOT / "upload.py"),
                         board["upload_profile"], board["com"], self.config["sketch"],
                         "--cli", self.config["arduino_cli"]],
                        self.config["flash_timeout_s"], log)

    def measure(self, board):
        self.event("measure", board=board["name"])
        command = [sys.executable, str(ROOT / "stlink_measure.py"), "capture",
                   "--port", self.config["stlink_com"], "--name", board["name"],
                   "--notes", board["notes"], "--out", str(self.directory / "measurements")]
        m = self.config["measurement"]
        for key in ("repeats", "seconds", "hz", "voltage", "warmup_seconds", "off_seconds"):
            command += ["--" + key.replace("_", "-"), str(m[key])]
        timeout = m["warmup_seconds"] + m["repeats"] * (m["seconds"] + m["off_seconds"] + 90) + 300
        with (self.directory / f"{board['name']}_measurement.log").open("w", encoding="utf-8") as log:
            run_command(command, timeout, log)

    def close(self):
        if self.serial is not None:
            self.serial.close()


def sequence(config, hardware):
    """All relays off -> all USB off -> flash each -> measure each -> all off."""
    try:
        hardware.open()
        for channel in range(config["numato_ports"]):
            hardware.relay(channel, False)
            hardware.pause()
        for port in config["ykush_ports"]:
            hardware.usb(port, False)
            hardware.pause()
        for board in config["connected_boards"]:
            hardware.usb(board["usb_port"], True)
            hardware.pause()
            hardware.wait_port(board["com"])
            hardware.flash(board)
            hardware.pause()
            hardware.usb(board["usb_port"], False)
            hardware.pause()
        for board in config["connected_boards"]:
            hardware.relay(board["relay"], True)
            hardware.pause()
            hardware.measure(board)
            hardware.pause()
            hardware.relay(board["relay"], False)
            hardware.pause()
    finally:
        failures = []
        for kind, channels in (("relay", range(config["numato_ports"])), ("usb", config["ykush_ports"])):
            for channel in channels:
                try:
                    getattr(hardware, kind)(channel, False)
                except Exception as error:
                    failures.append(f"{kind} {channel}: {error}")
        hardware.close()
        if failures:
            message = "Cleanup incomplete: " + "; ".join(failures)
            hardware.event("cleanup_error", message=message)
            if sys.exc_info()[0] is None:
                raise RuntimeError(message)


class DryRun(Hardware):
    def event(self, action, **details):
        print(action, details or "")

    def open(self):
        self.event("open Numato", port=self.config["numato_controller_port"])

    def pause(self):
        self.event("wait", seconds=self.config["step_delay_s"])

    def relay(self, channel, enabled):
        self.event("relay", channel=channel, enabled=enabled)

    def usb(self, port, enabled):
        self.event("USB", port=port, enabled=enabled, serial=self.config["ykush_serial"])

    def wait_port(self, port):
        self.event("wait for COM", port=port)

    def flash(self, board):
        self.event("upload", board=board["name"], port=board["com"], sketch=self.config["sketch"], profile=board["upload_profile"])

    def measure(self, board):
        self.event("measure", board=board["name"], stlink=self.config["stlink_com"], settings=self.config["measurement"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--dry-run", action="store_true", help="Print sequence without hardware access or uploads")
    parser.add_argument("--out", default=str(ROOT / "results"))
    args = parser.parse_args()
    config = load_config(args.config)
    if args.dry_run:
        sequence(config, DryRun(config, None))
        return
    for key in ("ykush_cmd", "arduino_cli"):
        if not shutil.which(config[key]):
            raise ValueError(f"{key}: executable not found: {config[key]}")
    if "REPLACE" in config["ykush_serial"]:
        raise ValueError("Set the actual YKUSH serial number in the configuration")
    directory = Path(args.out).resolve() / ("automation_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    directory.mkdir(parents=True)
    (directory / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"Logs and measurements: {directory}", flush=True)
    sequence(config, Hardware(config, directory))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted; cleanup attempted.", file=sys.stderr)
        sys.exit(130)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
