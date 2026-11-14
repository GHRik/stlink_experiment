"""Komunikacja ze STLINK-V3PWR i zapis strumienia pomiarowego.

Protokol: ST UM3291 API 1. Szczegoly transportu sa oddzielone od eksperymentu.
"""
from datetime import datetime, timezone
from pathlib import Path
import math
import re
import time
import csv
from storage import save_json

SAMPLE = re.compile(r"^(\d{4})([+-])(\d{1,2})$")
SOURCE = "https://www.st.com/resource/en/user_manual/um3291-getting-started-with-stlinkv3pwr-firmware-stmicroelectronics.pdf"


def normalize_line(line):
    """Firmware moze poprzedzac odpowiedz lub probke promptem stlp >."""
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
                raise RuntimeError("Brak koncow linii CRLF; sprawdz port SMU i format firmware.")

    def command(self, text, timeout=5):
        self.send(text)
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
            if line.lower().startswith("ack"):
                return line
        raise RuntimeError(f"Brak ACK dla {text!r}. Odpowiedzi: {received[-8:]}")

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
    try:
        # A full power cycle before EVERY repeat. AUX remains disabled.
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
                if now > start_clock + args.seconds + 30:
                    raise RuntimeError("Timeout: nie otrzymano wymaganej liczby probek i znacznika end.")
                if stop_sent and now > stop_clock + 10:
                    raise RuntimeError("Timeout po stop: brak znacznika end.")
                raw = device.line()
                if raw is None:
                    continue
                raw_out.write(raw)
                line = normalize_line(raw.decode("ascii", errors="strict"))
                value = decode_sample(line)
                if value is not None:
                    if count < n_target:
                        if not 0 <= value <= 0.6:
                            raise RuntimeError(f"Nieoczekiwana wartosc pradu: {value} A")
                        energy += value * args.voltage / args.hz
                        writer.writerow([count, f"{count / args.hz:.9f}",
                                         f"{value * 1e6:.9g}", args.voltage,
                                         f"{value * args.voltage * 1000:.9g}",
                                         f"{energy:.12g}"])
                        count += 1
                    if count >= n_target and not stop_sent:
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
                    raise RuntimeError(f"Urzadzenie: {line}")
                elif line.lower().startswith("ack"):
                    if "start" in line.lower():
                        started_ack = True
                elif line == "end":
                    ended = True
                    break
                elif line and not (line.startswith("pwr ") or line.startswith("summary")):
                    # Unknown metadata is retained; do not silently parse as current.
                    metadata["issues"].append(f"Nieznana linia protokolu: {line[:160]}")
                if now >= next_progress:
                    print(f"  {args.name} #{repeat}: {count / args.hz:.1f}/{args.seconds:g} s", flush=True)
                    next_progress = now + 5
        if not ended or count != n_target:
            metadata["issues"].append(f"Niepelna rejestracja: {count}/{n_target} probek.")
        if not started_ack:
            metadata["issues"].append("Brak rozpoznanego ACK start; sprawdz stream.bin.")
    except BaseException as exc:
        fatal = exc
        metadata["issues"].append(str(exc) or type(exc).__name__)
    finally:
        metadata["samples"] = count
        metadata["status"] = "valid" if ended and not metadata["issues"] else "invalid"
        save_json(directory / "metadata.json", metadata)
        save_json(directory / "commands.json", device.events)
    if fatal:
        raise fatal
    if metadata["status"] != "valid":
        raise RuntimeError(f"Pomiar oznaczony invalid: {directory}. Dane zachowane; sprawdz metadata.json.")
    return directory

def validate_settings(args):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.name):
        raise ValueError("--name: uzyj liter ASCII, cyfr, '-' lub '_'.")
    if not 1.6 <= args.voltage <= 3.6 or not math.isclose(args.voltage * 10, round(args.voltage * 10)):
        raise ValueError("Napiecie 1.6..3.6 V, krok 0.1 V.")
    if args.repeats < 1 or args.seconds <= 0 or args.seconds > 3600 or args.off_seconds < 0.1:
        raise ValueError("Powtorzenia >=1, czas 0..3600 s, czas odciecia >=0.1 s.")
    if not math.isclose(args.seconds * args.hz, round(args.seconds * args.hz)):
        raise ValueError("Czas * Hz musi byc calkowita liczba probek.")


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
        raise RuntimeError("To nie jest port pomiarowy STLINK-V3PWR.")
    if not re.search(r"apiver\s*:?\s*1\s*$", identity["apiver"], re.I):
        raise RuntimeError("Ten skrypt obsluguje tylko API 1.")
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
        raise RuntimeError(f"STLINK nie jest gotowy: {status}")


def save_session_settings(session, device, args, identity):
    save_json(session / "session_config.json",
              {"identity": identity, "commands": device.events,
               "arguments": vars(args), "source": SOURCE})
