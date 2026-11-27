"""Manual STLINK OUT control using the existing meter protocol."""
import re
from src.stlink_protocol import Device, identify_device


class MeterPower:
    def __init__(self):
        self._device = None
        self._port = None

    def get(self, port):
        # A monitoring connection must never use Device.close(): it powers OUT off.
        temporary = self._device is None or self._port != port
        device = Device(port) if temporary else self._device
        try:
            identity = device.command("whoami")
            if "STLINK-V3PWR" not in identity:
                raise RuntimeError("This is not an STLINK-V3PWR measurement port")
            response = device.command("pwr vout get")
            match = re.search(r"\b(on|off)\s*$", response, re.I)
            if not match:
                raise RuntimeError(f"Unknown STLINK OUT state: {response}")
            return {"port": port, "enabled": match[1].lower() == "on"}
        finally:
            if temporary:
                device.serial.close()

    def set(self, port, voltage, enabled):
        if enabled:
            voltage = float(voltage)
        if self._port != port:
            self.close()
        try:
            if self._device is None:
                self._device = Device(port)
                self._port = port
                identify_device(self._device)
                self._device.command("htc")
            self._device.command("pwr off")
            if enabled:
                self._device.command(f"volt vout {round(voltage * 1000)}m")
                self._device.command("pwr vout on")
            else:
                self.close()
        except BaseException:
            self.close()
            raise
        return {"port": port, "enabled": enabled, "voltage": voltage if enabled else None}

    def close(self):
        device, self._device = self._device, None
        self._port = None
        if device is not None:
            device.close()
