"""Enumerate serial ports without opening or probing connected devices."""
from serial.tools import list_ports


def available_ports():
    return [
        {"device": port.device, "description": port.description or "Unknown device",
         "hwid": port.hwid or ""}
        for port in sorted(list_ports.comports())
    ]
