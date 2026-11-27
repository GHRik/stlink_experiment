"""USB hub drivers. Physical USB sockets are numbered from one."""
from abc import ABC, abstractmethod
import re
import subprocess


def _run(command, timeout):
    return subprocess.run(command, check=True, capture_output=True,
                          text=True, timeout=timeout).stdout


class Hub(ABC):
    def __init__(self, ports):
        if (not isinstance(ports, list) or not ports
                or any(type(port) is not int or port <= 0 for port in ports)
                or len(set(ports)) != len(ports)):
            raise ValueError("Hub ports must be unique positive integer socket numbers")
        self.ports = list(ports)

    def open(self):
        """CLI-backed hubs need no persistent connection."""

    def set(self, port, enabled):
        if type(port) is not int or port not in self.ports:
            raise ValueError(f"USB port {port!r} is not configured for this hub")
        if type(enabled) is not bool:
            raise ValueError("USB state must be True or False")
        self._set(port, enabled)

    @abstractmethod
    def _set(self, port, enabled):
        """Switch one USB port and verify its state."""

    def close(self):
        """CLI-backed hubs need no persistent connection."""


class Ykush(Hub):
    def __init__(self, cmd, serial, ports, model_argument="ykush", command_runner=None, event=None):
        super().__init__(ports)
        if any(port > 3 for port in ports):
            raise ValueError("YKUSH ports must be between 1 and 3")
        if not isinstance(cmd, str) or not cmd.strip() or not isinstance(serial, str) or not serial.strip():
            raise ValueError("YKUSH executable and serial number are required")
        if model_argument not in ("", "ykush", "ykush3"):
            raise ValueError("Invalid YKUSH CLI model argument")
        self.command = [cmd] + ([model_argument] if model_argument else []) + ["-s", serial]
        self.run = command_runner or _run
        self.event = event or (lambda *args, **kwargs: None)

    def _set(self, port, enabled):
        response = self.run(self.command + ["-u" if enabled else "-d", str(port)], 15)
        status = self.run(self.command + ["-g", str(port)], 15)
        state = "ON" if enabled else "OFF"
        if not self._confirmed(status, port, state):
            raise RuntimeError(f"YKUSH port {port} state not confirmed: {status}")
        self.last_status = status.strip()
        self.event("ykush", port=port, enabled=enabled, response=response, status=status)

    def _confirmed(self, status, port, state):
        return re.search(rf"(?im)^\s*Downstream port\s+{port}\s+is\s+{state}\s*$", status)

    def get(self, port):
        if port not in self.ports:
            raise ValueError("USB port is not configured")
        status = self.run(self.command + ["-g", str(port)], 15)
        for state in ("ON", "OFF"):
            if self._confirmed(status, port, state):
                return state == "ON"
        raise RuntimeError(f"Unknown YKUSH state: {status}")


class Ykush3(Ykush):
    def __init__(self, cmd, serial, ports, command_runner=None, event=None):
        super().__init__(cmd, serial, ports, "ykush3", command_runner, event)

    def _confirmed(self, status, port, state):
        return (super()._confirmed(status, port, state)
                or re.search(rf"(?im)^\s*Port\s+{port}\s+{state}\s*$", status))


class YkushXs(Hub):
    """Single downstream port; CLI switches have no port-number argument."""

    def __init__(self, cmd, serial, ports, command_runner=None, event=None):
        super().__init__(ports)
        if ports != [1]:
            raise ValueError("YKUSH XS has one downstream port; ports must be [1]")
        if not isinstance(cmd, str) or not cmd.strip() or not isinstance(serial, str) or not serial.strip():
            raise ValueError("YKUSH executable and serial number are required")
        self.command = [cmd, "ykushxs", "-s", serial]
        self.run = command_runner or _run
        self.event = event or (lambda *args, **kwargs: None)

    def _set(self, port, enabled):
        response = self.run(self.command + ["-u" if enabled else "-d"], 15)
        status = self.run(self.command + ["-g"], 15)
        state = "ON" if enabled else "OFF"
        if not re.search(rf"(?im)^\s*Downstream port(?:\s+1)?\s+is\s+{state}\s*$", status):
            raise RuntimeError(f"YKUSH XS port state not confirmed: {status}")
        self.last_status = status.strip()
        self.event("ykush", port=port, enabled=enabled, response=response, status=status)

    def get(self, port):
        if port != 1:
            raise ValueError("YKUSH XS has one downstream port")
        status = self.run(self.command + ["-g"], 15)
        match = re.search(r"(?im)^\s*Downstream port(?:\s+1)?\s+is\s+(ON|OFF)\s*$", status)
        if not match:
            raise RuntimeError(f"Unknown YKUSH XS state: {status}")
        return match[1].upper() == "ON"


def create_hub(config, command_runner=None, event=None):
    driver = config["driver"]
    args = (config["cmd"], config["serial"], config["ports"])
    if driver == "ykushxs":
        if config.get("model_argument", "ykushxs") != "ykushxs":
            raise ValueError("YKUSH XS always uses the ykushxs CLI subcommand; remove model_argument")
        return YkushXs(*args, command_runner=command_runner, event=event)
    if driver == "ykush3":
        if config.get("model_argument", "ykush3") != "ykush3":
            raise ValueError("YKUSH3 always uses the ykush3 CLI subcommand; remove model_argument")
        return Ykush3(*args, command_runner=command_runner, event=event)
    if driver == "ykush":
        return Ykush(*args, model_argument=config.get("model_argument", "ykush"),
                     command_runner=command_runner, event=event)
    raise ValueError(f"Unknown hub driver: {driver!r}; use ykush, ykush3 or ykushxs")
