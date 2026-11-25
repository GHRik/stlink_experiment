"""YKUSH discovery protocol checks using vendor CLI response examples."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from automation.backend.hub_discovery import available_hubs


class HubDiscoveryTests(unittest.TestCase):
    @patch("automation.backend.hub_discovery.shutil.which", return_value="ykushcmd.exe")
    @patch("automation.backend.hub_discovery.subprocess.run")
    def test_legacy_list_and_unique_serials(self, run, which):
        run.return_value = SimpleNamespace(returncode=0, stderr="", stdout=(
            "Attached YKUSH Boards:\n1. Board found with serial number: YK17125\n"
            "2. Board found with serial number: YK21493\n3. Board found with serial number: YK17125\n"))
        self.assertEqual(available_hubs("ykush"), [{"serial": "YK17125"}, {"serial": "YK21493"}])
        self.assertEqual(run.call_args.args[0], ["ykushcmd.exe", "-l"])
        self.assertFalse(run.call_args.kwargs.get("shell", False))

    @patch("automation.backend.hub_discovery.shutil.which", return_value="C:/vendor tools/ykushcmd.exe")
    @patch("automation.backend.hub_discovery.subprocess.run")
    def test_ykush3_subcommand(self, run, which):
        run.return_value = SimpleNamespace(returncode=0, stderr="", stdout="Serial Number: YK00009\n")
        self.assertEqual(available_hubs("ykush3", "C:/vendor tools/ykushcmd.exe"), [{"serial": "YK00009"}])
        self.assertEqual(run.call_args.args[0], ["C:/vendor tools/ykushcmd.exe", "ykush3", "-l"])

    @patch("automation.backend.hub_discovery.shutil.which", return_value="ykushcmd.exe")
    @patch("automation.backend.hub_discovery.subprocess.run")
    def test_no_boards(self, run, which):
        run.return_value = SimpleNamespace(returncode=0, stderr="", stdout="Attached YKUSH Boards:\n")
        self.assertEqual(available_hubs("ykush"), [])

    @patch("automation.backend.hub_discovery.shutil.which", return_value="ykushcmd.exe")
    @patch("automation.backend.hub_discovery.subprocess.run")
    def test_cli_failure_reports_diagnostic(self, run, which):
        run.return_value = SimpleNamespace(returncode=1, stderr="USB enumeration failed", stdout="")
        with self.assertRaisesRegex(RuntimeError, "USB enumeration failed"):
            available_hubs("ykush")

    def test_unsupported_model(self):
        with self.assertRaises(ValueError):
            available_hubs("other")

    @patch("automation.backend.hub_discovery.shutil.which", return_value=None)
    def test_missing_custom_executable(self, which):
        with self.assertRaisesRegex(FileNotFoundError, "not found"):
            available_hubs("ykush", "C:/missing/ykushcmd.exe")
