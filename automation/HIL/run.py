"""Sequential firmware upload and STLINK measurement through USB and relay switches."""
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

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.HIL.relays import create_relay
from automation.HIL.hubs import create_hub
from src.events import emit


def read_config(path):
    """JSON with optional full-line // comments; preserve JSON error line numbers."""
    text = Path(path).read_text(encoding="utf-8-sig")
    text = "\n".join("" if line.lstrip().startswith("//") else line for line in text.splitlines())
    return json.loads(text)


def load_config(path):
    path = Path(path).resolve()
    config = read_config(path)
    if "stlink" in config and ("hub" in config or "ykush" in config):
        hub_config = config.get("hub")
        if hub_config is None:
            old_hub = config["ykush"]
            model = old_hub.get("model_argument", "")
            hub_config = dict(old_hub, driver=model if model in ("ykush3", "ykushxs") else "ykush")
        relay_config = config.get("relay_controller")
        if relay_config is None:
            old = config["numato"]
            relay_config = dict(driver="numato", port=old["controller_port"],
                                channels=old["ports"], channel_digits=old["channel_digits"])
        # Keep the execution layer independent of the human-facing config layout.
        config = {
            "hub": hub_config,
            "relay_controller": relay_config,
            "stlink_com": config["stlink"]["com"],
            "measurement": config["stlink"]["measurement"],
            "arduino_cli": config["upload"]["arduino_cli"],
            "flash_timeout_s": config["upload"]["timeout_s"],
            "step_delay_s": config["timing"]["step_delay_s"],
            "port_timeout_s": config["timing"]["port_timeout_s"],
            "connected_boards": config["connected_boards"],
        }
    boards = config["connected_boards"]
    if not isinstance(boards, list) or not 1 <= len(boards) <= 3:
        raise ValueError("connected_boards must contain 1 to 3 board mappings")
    if "relay_controller" not in config:
        config["relay_controller"] = dict(driver="numato", port=config["numato_controller_port"],
                                          channels=config["numato_ports"], channel_digits=config["numato_channel_digits"])
    relay_config = config["relay_controller"]
    create_relay(relay_config)  # Validate driver settings without opening the device.
    count = relay_config["channels"]
    if "hub" not in config:
        model = config["ykush_model_argument"]
        config["hub"] = dict(driver=model if model in ("ykush3", "ykushxs") else "ykush",
                             cmd=config["ykush_cmd"], serial=config["ykush_serial"],
                             model_argument=model, ports=config["ykush_ports"])
    create_hub(config["hub"])  # Validate without sending any USB command.
    ports = config["hub"]["ports"]
    for field in ("name", "ykush_usb_port", "com", "relay"):
        values = [board[field] for board in boards]
        if len(set(str(v).upper() for v in values)) != len(values):
            raise ValueError(f"Board {field} values must be unique")
    device_ports = [config["stlink_com"], relay_config["port"], *[b["com"] for b in boards]]
    if any(not isinstance(p, str) or not p.strip() for p in device_ports) or len(set(p.upper() for p in device_ports)) != len(device_ports):
        raise ValueError("STLINK, relay controller and board COM ports must be distinct and nonempty")
    for board in boards:
        board["sketch"] = str((path.parent / board["sketch"]).resolve())
        board.setdefault("notes", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", board["name"]):
            raise ValueError("Each board needs an ASCII name")
        if type(board["ykush_usb_port"]) is not int or board["ykush_usb_port"] not in ports:
            raise ValueError("Board ykush_usb_port is not in hub.ports")
        if type(board["relay"]) is not int or not 0 <= board["relay"] < count:
            raise ValueError("Board relay must be a zero-based controller channel")
    from automation.HIL.upload import load_profiles
    profiles = load_profiles()
    for board in boards:
        if board.get("upload_profile") not in profiles:
            raise ValueError(f"Board {board['name']}: upload_profile must match a profile in automation/HIL/board_profiles.json")
    for field in ("step_delay_s", "port_timeout_s", "flash_timeout_s"):
        if not math.isfinite(config[field]) or config[field] <= 0:
            raise ValueError(f"{field} must be positive and finite")
    # Use the existing measurement validator before switching any hardware.
    from src.stlink_protocol import validate_settings
    m = config["measurement"]
    for board in boards:
        validate_settings(argparse.Namespace(name=board["name"], repeats=m["repeats"],
                          seconds=m["seconds"], hz=m["hz"], voltage=m["voltage"],
                          off_seconds=m["off_seconds"], warmup_seconds=m["warmup_seconds"]))
    if type(m["repeats"]) is not int or m["hz"] not in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000):
        raise ValueError("Invalid repeat count or sampling frequency")
    return config


def run_command(command, timeout, log=None, cwd=None):
    """Terminate the process tree on timeout or interruption before disconnecting power."""
    process = subprocess.Popen(command, stdout=log or subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True,
                               start_new_session=os.name != "nt", cwd=cwd)
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
        self.relays = None
        self.hub = create_hub(config["hub"], run_command, self.event)

    def event(self, action, **details):
        print(action, details or "", flush=True)
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),
                                       monotonic_s=time.monotonic(), action=action, **details)) + "\n")

    def pause(self):
        time.sleep(self.config["step_delay_s"])

    def open(self):
        self.hub.open()
        self.relays = create_relay(self.config["relay_controller"], self.event)
        self.relays.open()

    def relay(self, channel, enabled):
        self.relays.set(channel, enabled)
        emit("relay", channel=channel, enabled=enabled)

    def usb(self, port, enabled):
        self.hub.set(port, enabled)
        emit("hub", serial=self.config["hub"]["serial"], port=port, enabled=enabled)

    def wait_port(self, port):
        from serial.tools.list_ports import comports
        deadline = time.monotonic() + self.config["port_timeout_s"]
        while time.monotonic() < deadline:
            if port.upper() in {p.device.upper() for p in comports()}:
                return
            time.sleep(.2)
        raise RuntimeError(f"Board upload port did not appear: {port}")

    def flash(self, board):
        emit("upload", state="started", name=board["name"])
        self.event("flash", board=board["name"], port=board["com"])
        with (self.directory / f"{board['name']}_upload.log").open("w", encoding="utf-8") as log:
            run_command([sys.executable, "-u", str(ROOT / "automation/HIL/upload.py"),
                         board["upload_profile"], board["com"], board["sketch"],
                         "--cli", self.config["arduino_cli"]],
                        self.config["flash_timeout_s"], log)
        emit("upload", state="completed", name=board["name"])

    def measure(self, board):
        self.event("measure", board=board["name"])
        command = [sys.executable, "-m", "src.stlink_measure", "capture",
                   "--port", self.config["stlink_com"], "--name", board["name"],
                   "--notes", board["notes"], "--out", str(self.directory / "measurements")]
        m = self.config["measurement"]
        for key in ("repeats", "seconds", "hz", "voltage", "warmup_seconds", "off_seconds"):
            command += ["--" + key.replace("_", "-"), str(m[key])]
        if m.get("controller"):
            command += ["--controller", m["controller"]]
        timeout = m["warmup_seconds"] + m["repeats"] * (m["seconds"] + m["off_seconds"] + 90) + 300
        with (self.directory / f"{board['name']}_measurement.log").open("w", encoding="utf-8") as log:
            run_command(command, timeout, log, cwd=ROOT)

    def close(self):
        try:
            if self.relays is not None:
                self.relays.close()
        finally:
            self.hub.close()


def sequence(config, hardware):
    """All relays off -> all USB off -> flash each -> measure each -> all off."""
    try:
        hardware.open()
        for channel in range(config["relay_controller"]["channels"]):
            hardware.relay(channel, False)
            hardware.pause()
        for port in config["hub"]["ports"]:
            hardware.usb(port, False)
            hardware.pause()
        for board in config["connected_boards"]:
            hardware.usb(board["ykush_usb_port"], True)
            hardware.pause()
            hardware.wait_port(board["com"])
            hardware.flash(board)
            hardware.pause()
            hardware.usb(board["ykush_usb_port"], False)
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
        for kind, channels in (("relay", range(config["relay_controller"]["channels"])), ("usb", config["hub"]["ports"])):
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
        self.event("open relay controller", **self.config["relay_controller"])

    def pause(self):
        self.event("wait", seconds=self.config["step_delay_s"])

    def relay(self, channel, enabled):
        self.event("relay", channel=channel, enabled=enabled)

    def usb(self, port, enabled):
        self.event("USB", port=port, enabled=enabled, driver=self.config["hub"]["driver"], serial=self.config["hub"]["serial"])

    def wait_port(self, port):
        self.event("wait for COM", port=port)

    def flash(self, board):
        self.event("upload", board=board["name"], port=board["com"], sketch=board["sketch"], profile=board["upload_profile"])

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
    if config["arduino_cli"] == "arduino-cli":
        from automation.HIL.upload import default_arduino_cli
        config["arduino_cli"] = default_arduino_cli()
    for key, executable in (("hub.cmd", config["hub"]["cmd"]), ("arduino_cli", config["arduino_cli"])):
        if not shutil.which(executable):
            raise ValueError(f"{key}: executable not found: {executable}")
    if "REPLACE" in config["hub"]["serial"]:
        raise ValueError("Set the actual YKUSH serial number in the configuration")
    directory = Path(args.out).resolve() / ("automation_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    directory.mkdir(parents=True)
    (directory / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"Logs and measurements: {directory}", flush=True)
    sequence(config, Hardware(config, directory))


def cli():
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted; cleanup attempted.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(cli())
