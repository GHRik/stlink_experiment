import unittest
from unittest.mock import patch

from automation import upload


class UploadTests(unittest.TestCase):
    def test_uploader_forwards_cli_diagnostics_and_exit_code(self):
        with patch.object(upload.subprocess, "run") as command:
            command.return_value.returncode = 7
            result = upload.main(["nodemcu", "COM22", "path with spaces/sketch.ino",
                                  "--cli", "arduino-cli.exe"])
            self.assertEqual(result, 7)
            command.assert_called_once_with([
                "arduino-cli.exe", "compile", "--upload", "--verbose", "--fqbn",
                "esp8266:esp8266:nodemcuv2:xtal=80,wipe=all,baud=115200",
                "--port", "COM22", "path with spaces/sketch.ino"])


if __name__ == "__main__":
    unittest.main()
