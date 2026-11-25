"""Manual STLINK OUT control using the existing meter protocol."""
from src.stlink_protocol import Device, identify_device


class MeterPower:
    def __init__(self):
        self._device = None
        self._port = None

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
