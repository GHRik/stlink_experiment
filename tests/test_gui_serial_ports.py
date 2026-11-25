"""Serial discovery and desktop API checks without attached devices."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from serial.tools.list_ports_common import ListPortInfo

from automation.backend.api import DesktopApi
from automation.backend.serial_ports import available_ports


class SerialPortTests(unittest.TestCase):
    @patch("automation.backend.serial_ports.list_ports.comports")
    def test_ports_are_naturally_sorted_and_include_descriptions(self, comports):
        first, second = ListPortInfo("COM2"), ListPortInfo("COM10")
        first.description = "STLINK SMU"
        first.hwid = "USB VID:PID=0483:374E"
        comports.return_value = [second, first]
        ports = available_ports()
        self.assertEqual([port["device"] for port in ports], ["COM2", "COM10"])
        self.assertEqual(ports[0]["description"], "STLINK SMU")
        self.assertEqual(ports[0]["hwid"], first.hwid)

    @patch("automation.backend.serial_ports.list_ports.comports", return_value=[])
    def test_no_connected_ports(self, comports):
        self.assertEqual(available_ports(), [])

    @patch("automation.backend.api.available_ports", return_value=[{"device": "COM7"}])
    def test_api_exposes_discovery(self, discover):
        self.assertEqual(DesktopApi(Mock()).list_ports(), [{"device": "COM7"}])

    def test_api_preserves_native_file_selection(self):
        api = DesktopApi(SimpleNamespace(FileDialog=SimpleNamespace(OPEN="open")))
        window = Mock()
        window.create_file_dialog.return_value = None
        api._bind_window(window)
        self.assertIsNone(api.pick_file("sketch"))
        window.create_file_dialog.assert_called_once()

    @patch("automation.backend.api.available_hubs", return_value=[])
    def test_discovery_uses_configured_executable(self, discover):
        api = DesktopApi(Mock(), {"hub": {"cmd": "C:/tools/ykushcmd.exe"}})
        api.list_hubs("ykush3")
        discover.assert_called_once_with("ykush3", "C:/tools/ykushcmd.exe")

    @patch("automation.backend.api.HubControl")
    def test_switch_uses_backend_default_command(self, control):
        api = DesktopApi(Mock())
        api.set_hub_port("ykush", "YK17125", 2, False)
        control.return_value.set_port.assert_called_once_with("ykush", "ykushcmd", "YK17125", 2, False)
