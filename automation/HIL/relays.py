"""Relay drivers. Public channel numbers are zero-based for both devices."""
from abc import ABC, abstractmethod
import re

import serial


class Relay(ABC):
    baudrate = None

    def __init__(self, port, channels, event=None):
        if not isinstance(port, str) or not port.strip():
            raise ValueError("Relay controller port must not be empty")
        if type(channels) is not int or not 1 <= channels <= 64:
            raise ValueError("Relay channels must be an integer from 1 to 64")
        self.port, self.channels = port, channels
        self.event = event or (lambda *args, **kwargs: None)
        self.serial = None

    def open(self):
        self.serial = serial.Serial(self.port, self.baudrate, timeout=2, write_timeout=3)

    def write(self, data):
        if self.serial.write(data) != len(data):
            raise IOError("Incomplete relay command")
        self.serial.flush()

    def set(self, channel, enabled):
        if type(channel) is not int or not 0 <= channel < self.channels:
            raise ValueError(f"Relay channel must be between 0 and {self.channels - 1}")
        if type(enabled) is not bool:
            raise ValueError("Relay state must be True or False")
        self._set(channel, enabled)

    @abstractmethod
    def _set(self, channel, enabled):
        """Switch exactly one physical relay."""

    def close(self):
        if self.serial is not None:
            self.serial.close()


class NumatoRelay(Relay):
    baudrate = 19200

    def __init__(self, port, channels, channel_digits=1, event=None):
        super().__init__(port, channels, event)
        if channel_digits not in (1, 2, 3):
            raise ValueError("Numato channel_digits must be 1, 2 or 3")
        self.channel_digits = channel_digits

    def command(self, text):
        self.serial.reset_input_buffer()
        self.write((text + "\r").encode("ascii"))
        response = self.serial.read_until(b">").decode("ascii", errors="replace")
        self.event("numato", command=text, response=response)
        if not response.endswith(">") or re.search(r"error|invalid|unknown", response, re.I):
            raise RuntimeError(f"Numato command failed: {text!r}: {response!r}")
        return response

    def _set(self, channel, enabled):
        state = "on" if enabled else "off"
        index = f"{channel:0{self.channel_digits}d}"
        self.command(f"relay {state} {index}")
        response = self.command(f"relay read {index}")
        states = re.findall(r"(?im)^\s*(on|off)\s*$", response.replace(">", ""))
        if not states or states[-1].lower() != state:
            raise RuntimeError(f"Numato relay {channel} did not confirm {state}")


class Lcus2Relay(Relay):
    baudrate = 9600

    def __init__(self, port, channels=2, event=None):
        super().__init__(port, channels, event)
        if channels > 2:
            raise ValueError("LCUS-2 has only two relay channels")

    def _set(self, channel, enabled):
        address, state = channel + 1, int(enabled)
        packet = bytes([0xA0, address, state, (0xA0 + address + state) & 0xFF])
        self.write(packet)
        self.event("lcus2", channel=channel, enabled=enabled,
                   command_hex=packet.hex(" "), confirmation="write_and_flush")


def create_relay(config, event=None):
    driver = config["driver"]
    if driver == "numato":
        return NumatoRelay(config["port"], config["channels"],
                           config.get("channel_digits", 1), event)
    if driver == "lcus2":
        return Lcus2Relay(config["port"], config["channels"], event)
    raise ValueError(f"Unknown relay driver: {driver!r}; use numato or lcus2")
