import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from automation.HIL import upload


class UploadTests(unittest.TestCase):
    def test_finds_arduino_ide_bundle_when_cli_is_not_on_path(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'Programs/Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe'
            executable.parent.mkdir(parents=True)
            executable.touch()
            with patch.dict(upload.os.environ, {'LOCALAPPDATA': directory}, clear=True), \
                 patch.object(upload.shutil, 'which', return_value=None):
                self.assertEqual(upload.default_arduino_cli(), str(executable))

    def test_environment_override_has_priority(self):
        with patch.dict(upload.os.environ, {'ARDUINO_CLI': 'C:/custom/arduino-cli.exe'}):
            self.assertEqual(upload.default_arduino_cli(), 'C:/custom/arduino-cli.exe')

    def test_compilation_failure_skips_upload_and_preserves_exit_code(self):
        with patch.object(upload.subprocess, "run") as command:
            command.return_value.returncode = 7
            result = upload.main(["nodemcu", "COM22", "path with spaces/sketch.ino",
                                  "--cli", "arduino-cli.exe"])
            self.assertEqual(result, 7)
            self.assertEqual(command.call_count, 1)
            self.assertEqual(command.call_args.args[0][:5], [
                "arduino-cli.exe", "compile", "--verbose", "--fqbn",
                "esp8266:esp8266:nodemcuv2:xtal=80,wipe=all,baud=115200"])
            self.assertEqual(command.call_args.args[0][-1], "path with spaces/sketch.ino")

    def test_upload_failure_is_not_masked_by_successful_compilation(self):
        with patch.object(upload.subprocess, 'run') as command:
            from types import SimpleNamespace
            command.side_effect = [SimpleNamespace(returncode=0), SimpleNamespace(returncode=2)]
            result = upload.main(['nodemcu', 'COM17', 'path with spaces/sketch.ino', '--cli', 'arduino-cli.exe'])
            self.assertEqual(result, 2)
            compile_args = command.call_args_list[0].args[0]
            upload_args = command.call_args_list[1].args[0]
            self.assertEqual(upload_args[1], 'upload')
            self.assertEqual(upload_args[upload_args.index('--port') + 1], 'COM17')
            self.assertEqual(upload_args[upload_args.index('--input-dir') + 1],
                             compile_args[compile_args.index('--build-path') + 1])


if __name__ == "__main__":
    unittest.main()
