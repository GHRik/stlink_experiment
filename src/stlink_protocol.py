"""STLINK-V3PWR communication and acquisition stream recording.

Protocol: ST UM3291 API 1. Transport details are separate from experiment orchestration.
"""
from datetime import datetime, timezone
from pathlib import Path
import math
import re
import time
import csv
from .storage import save_json
from .measurement_controller import MeasurementController
from .events import emit

SAMPLE = re.compile(r"^(\d{4})([+-])(\d{1,2})$")
SOURCE = "https://www.st.com/resource/en/user_manual/um3291-getting-started-with-stlinkv3pwr-firmware-stmicroelectronics.pdf"


def normalize_line(line):
    """Firmware may prefix a response or sample with the stlp > prompt."""
    return re.sub(r"^(?:stlp\s*>\s*)+", "", line.strip(), flags=re.I).strip()

def decode_sample(line):
    match = SAMPLE.fullmatch(normalize_line(line))
    if not match:
        return None
    mantissa, sign, exponent = match.groups()
    return int(mantissa) * 10.0 ** (int(exponent) * (1 if sign == "+" else -1))

class Device:
    def __init__(self, port):
        import serial
        self.serial = serial.Serial(port, 115200, timeout=0.1, write_timeout=3)
        self.pending = bytearray()
        self.events = []

    def send(self, command):
        self.events.append({"host_monotonic_s": time.monotonic(), "tx": command})
        self.serial.write((command + "\r\n").encode("ascii"))
        self.serial.flush()

    def line(self):
        while True:
            pos = self.pending.find(b"\n")
            if pos >= 0:
                raw = bytes(self.pending[:pos + 1])
                del self.pending[:pos + 1]
                return raw
            chunk = self.serial.read(max(1, min(self.serial.in_waiting, 65536)))
            if not chunk:
                return None
            self.pending.extend(chunk)
            if len(self.pending) > 100000:
                raise RuntimeError("Missing CRLF line endings; check the SMU port and firmware data format.")

    def command(self, text, timeout=5):
        self.send(text)
        expected = "STLINK-V3PWR" if text.split()[0] == "whoami" else text.split()[0]
        deadline = time.monotonic() + timeout
        received = []
        while time.monotonic() < deadline:
            raw = self.line()
            if raw is None:
                continue
            line = normalize_line(raw.decode("ascii", errors="replace"))
            if line:
                received.append(line)
                self.events.append({"rx": line})
            if line.lower().startswith("err"):
                raise RuntimeError(f"{text}: {line}")
            if re.match(r"^ack\s+" + re.escape(expected) + r"(?:\s|:|$)", line, re.I):
                if text in ("pwr off", "pwr vout on"):
                    emit("meter_power", enabled=text == "pwr vout on")
                return line
        raise RuntimeError(f"No acknowledgement for {text!r}. Responses: {received[-8:]}")

    def drain(self, seconds=0.5):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.serial.read(max(1, min(self.serial.in_waiting, 65536)))
        self.pending.clear()

    def close(self):
        # Best effort on normal exit, Ctrl+C, parser failure or timeout.
        for command in ("stop", "pwr off", "hrc"):
            try:
                self.command(command, timeout=2)
            except Exception:
                pass
        self.serial.close()

def read_temperature(device):
    reply = device.command("temp degc refresh")
    match = re.search(r"\btemp\b.*?([-+]?\d+(?:\.\d+)?)\s*(?:°?\s*[Cc]|degc)?\s*$", reply, re.I)
    if not match:
        raise RuntimeError(f"Cannot decode fresh meter temperature: {reply}")
    return float(match.group(1))


def warm_up(device, seconds):
    """Warm up once per series, without acquiring samples; AUX stays off."""
    before = read_temperature(device)
    emit("warmup", state="started", seconds=seconds, elapsed=0)
    if seconds > 0:
        print(f"Warming up for {seconds:g} s with OUT enabled (target is running).", flush=True)
        device.command("pwr vout on")
        try:
            remaining = seconds
            while remaining > 0:
                step = min(10, remaining)
                time.sleep(step)
                remaining -= step
                emit("warmup", state="progress", seconds=seconds, elapsed=seconds - remaining)
                print(f"  Warm-up: {seconds - remaining:g}/{seconds:g} s", flush=True)
        finally:
            device.command("pwr off")
    emit("warmup", state="completed", seconds=seconds, elapsed=seconds)
    return {"requested_seconds": seconds, "temperature_before_C": before,
            "temperature_after_C": read_temperature(device)}


def capture_one(device, directory, args, identity, repeat):
    directory.mkdir()
    n_target = round(args.seconds * args.hz)
    metadata = {
        "configuration": args.name, "repeat": repeat,
        "utc": datetime.now(timezone.utc).isoformat(),
        "voltage_V": args.voltage, "sampling_Hz": args.hz,
        "requested_duration_s": n_target / args.hz,
        "power_off_s": args.off_seconds, "identity": identity,
        "board_notes": args.notes, "protocol": "UM3291 API 1, ascii_dec, current",
        "time_origin": "First acquired sample interval; automatic OUT power-on at acquisition start. Not an independently measured voltage edge.",
        "energy_method": "Sum(current_A * nominal_voltage_V / sampling_Hz). Rectangular numerical estimate.",
        "status": "incomplete", "issues": [],
    }
    save_json(directory / "metadata.json", metadata)
    device.events = []
    count = 0
    ended = False
    started_ack = False
    start_clock = time.monotonic()
    stop_sent = False
    stop_clock = None
    next_progress = start_clock + 5
    energy = 0.0
    fatal = None
    controller_path = getattr(args, "controller", None)
    controller = MeasurementController(controller_path, directory, args.seconds) if controller_path else None
    try:
        # A full power cycle before EVERY repeat. AUX remains disabled.
        device.command("pwr off")
        metadata["temperature_before_calibration_C"] = read_temperature(device)
        metadata["calibration"] = {"status": "started", "utc": datetime.now(timezone.utc).isoformat()}
        print(f"  Calibrating before repeat {repeat}...", flush=True)
        emit("calibration", state="started", repeat=repeat)
        # Verified on V4.J7.B3.P6: calib returns "error calib" with OUT off.
        # Keep AUX off; power-cycle the target AFTER calibration for the capture.
        device.command("pwr vout on")
        time.sleep(1)
        reply = device.command("calib", timeout=30)
        if not re.match(r"^ack\s+calib\b", reply, re.I):
            raise RuntimeError(f"Unexpected calibration acknowledgement: {reply}")
        # Allow trailing firmware messages to settle, then check device readiness.
        device.drain(1)
        status = device.command("status")
        if not re.search(r"\bstatus\s*:?\s*ok\s*$", status, re.I):
            raise RuntimeError(f"Meter not ready after calibration: {status}")
        metadata["calibration"].update(status="acknowledged", response=reply, device_status=status)
        emit("calibration", state="completed", repeat=repeat)
        metadata["temperature_before_C"] = read_temperature(device)
        device.command("pwr off")
        time.sleep(args.off_seconds)
        device.command("pwr vout auto")
        device.command("pwrend off")
        device.drain(0.2)
        with (directory / "stream.bin").open("wb") as raw_out, (directory / "samples.csv").open(
            "w", newline="", encoding="utf-8-sig"
        ) as csv_out:
            writer = csv.writer(csv_out, delimiter=";")
            writer.writerow(["sample_index", "time_s", "current_uA", "voltage_V",
                             "power_mW", "energy_estimate_J"])
            device.send("start")
            start_clock = time.monotonic()
            next_progress = start_clock + 5
            while True:
                now = time.monotonic()
                if controller is not None and controller.process is not None:
                    controller.check()
                if now > start_clock + args.seconds + 30:
                    raise RuntimeError("Timeout: the required sample count and end marker were not received.")
                if stop_sent and now > stop_clock + 10:
                    raise RuntimeError("Timeout after stop: missing end marker.")
                raw = device.line()
                if raw is None:
                    continue
                raw_out.write(raw)
                line = normalize_line(raw.decode("ascii", errors="strict"))
                value = decode_sample(line)
                if value is not None:
                    if count < n_target:
                        if not 0 <= value <= 0.6:
                            raise RuntimeError(f"Unexpected current value: {value} A")
                        energy += value * args.voltage / args.hz
                        writer.writerow([count, f"{count / args.hz:.9f}",
                                         f"{value * 1e6:.9g}", args.voltage,
                                         f"{value * args.voltage * 1000:.9g}",
                                         f"{energy:.12g}"])
                        count += 1
                    if count >= n_target and not stop_sent:
                        if controller is not None:
                            controller.request_stop()
                        device.send("stop")
                        stop_sent = True
                        stop_clock = time.monotonic()
                elif re.match(r"^RecID(?:\s|:)", line, re.I):
                    # Conservative: do not fabricate a gap-free time axis.
                    if count < n_target:
                        metadata["issues"].append(
                            f"Sample resynchronization after calibration or data loss: {line}. "
                            "The continuous sample time axis cannot be guaranteed; repeat this measurement.")
                elif line.lower().startswith("warning:") and "calibration" in line.lower():
                    if count < n_target:
                        metadata["issues"].append(
                            f"Device calibration warning: {line}. "
                            "Acquisition continuity must be verified; repeat this measurement.")
                elif line.lower().startswith("err"):
                    raise RuntimeError(f"Device error: {line}")
                elif line.lower().startswith("ack"):
                    if "start" in line.lower():
                        if not started_ack:
                            emit("meter_power", enabled=True)
                            emit("repeat", state="started", repeat=repeat, elapsed=0, seconds=args.seconds)
                        if not started_ack and controller is not None:
                            controller.start()
                        started_ack = True
                elif line == "end":
                    emit("meter_power", enabled=False)
                    ended = True
                    break
                elif line and not (line.startswith("pwr ") or line.startswith("summary")):
                    # Unknown metadata is retained; do not silently parse as current.
                    metadata["issues"].append(f"Unknown protocol line: {line[:160]}")
                if now >= next_progress:
                    emit("repeat", state="progress", repeat=repeat, elapsed=count / args.hz, seconds=args.seconds)
                    print(f"  {args.name} #{repeat}: {count / args.hz:.1f}/{args.seconds:g} s", flush=True)
                    next_progress = now + 5
        if not ended or count != n_target:
            metadata["issues"].append(f"Incomplete capture: {count}/{n_target} samples.")
        if not started_ack:
            metadata["issues"].append("Missing start acknowledgement; check stream.bin.")
        metadata["temperature_after_C"] = read_temperature(device)
    except BaseException as exc:
        fatal = exc
        metadata["issues"].append(str(exc) or type(exc).__name__)
        if metadata.get("calibration", {}).get("status") == "started":
            metadata["calibration"]["status"] = "failed"
    finally:
        if fatal:
            try:
                device.command("pwr off")
            except Exception:
                pass
        metadata["samples"] = count
        if controller is not None:
            try:
                metadata["controller"] = controller.close()
                outcome = metadata["controller"]
                if outcome and (outcome["forced_stop"] or outcome["returncode"] != 0):
                    metadata["issues"].append("Controller failed or required forced termination; see controller.log.")
            except Exception as error:
                metadata["issues"].append(f"Controller cleanup failed: {error}")
        metadata["status"] = "valid" if ended and not metadata["issues"] else "invalid"
        save_json(directory / "metadata.json", metadata)
        save_json(directory / "commands.json", device.events)
    if fatal:
        raise fatal
    if metadata["status"] != "valid":
        raise RuntimeError(f"Measurement marked invalid: {directory}. Data preserved; check metadata.json.")
    return directory

def validate_settings(args):
    controller = getattr(args, "controller", None)
    if controller and (not Path(controller).is_file() or Path(controller).suffix.lower() != ".py"):
        raise ValueError("--controller must point to an existing Python (.py) file.")
    warmup = getattr(args, "warmup_seconds", 180)
    if not math.isfinite(warmup) or not 0 <= warmup <= 3600:
        raise ValueError("--warmup-seconds must be between 0 and 3600.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.name):
        raise ValueError("--name: use ASCII letters, digits, '-' or '_'.")
    if not 1.6 <= args.voltage <= 3.6 or not math.isclose(args.voltage * 10, round(args.voltage * 10)):
        raise ValueError("Voltage must be between 1.6 and 3.6 V in 0.1 V increments.")
    if args.repeats < 1 or args.seconds <= 0 or args.seconds > 3600 or args.off_seconds < 0.1:
        raise ValueError("Repeats must be >= 1, duration > 0 and <= 3600 s, and power-off time >= 0.1 s.")
    if not math.isclose(args.seconds * args.hz, round(args.seconds * args.hz)):
        raise ValueError("Duration multiplied by sampling rate must be a whole number of samples.")


def create_session(args):
    session = Path(args.out) / (args.name + "_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    session.mkdir(parents=True)
    return session


def identify_device(device):
    device.send("stop")
    device.drain(1)
    device.command("status")
    identity = {key: device.command(key) for key in ("whoami", "version", "apiver")}
    if "STLINK-V3PWR" not in identity["whoami"]:
        raise RuntimeError("This is not an STLINK-V3PWR measurement port.")
    if not re.search(r"apiver\s*:?\s*1\s*$", identity["apiver"], re.I):
        raise RuntimeError("This script supports only API version 1.")
    return identity


def configure_device(device, args):
    device.command("htc")
    device.command("pwr off")
    device.command(f"volt vout {round(args.voltage * 1000)}m")
    device.command("format ascii_dec")
    device.command(f"freq {args.hz}")
    device.command("output current")
    device.command("acqtime inf")
    device.command("trigsrc sw")
    device.command("trigdelay 0")
    status = device.command("status")
    if "error" in status.lower():
        raise RuntimeError(f"STLINK is not ready: {status}")


def save_session_settings(session, device, args, identity):
    save_json(session / "session_config.json",
              {"identity": identity, "commands": device.events,
               "arguments": vars(args), "source": SOURCE})
