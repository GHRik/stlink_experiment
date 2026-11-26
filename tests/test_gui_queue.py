"""Queue uses existing runners; only native path selection/validation is new backend work."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from automation.backend.file_picker import FilePicker
from automation.backend.capture import capture_command
from automation.backend.api import DesktopApi
from tests.test_gui_hil import gui_configuration


class QueueFileTests(unittest.TestCase):
    def test_multiple_selection_returns_full_paths_and_cancel_is_empty(self):
        picker=FilePicker(Mock());picker._window=Mock()
        picker._window.create_file_dialog.return_value=['one.ino','two.ino']
        self.assertEqual(picker.pick_sketches(),[str(Path(name).resolve()) for name in ('one.ino','two.ino')])
        self.assertTrue(picker._window.create_file_dialog.call_args.kwargs['allow_multiple'])
        picker._window.create_file_dialog.return_value=None
        self.assertEqual(picker.pick_sketches(),[])

    def test_all_paths_are_checked_before_running(self):
        picker=FilePicker(Mock())
        with self.assertRaisesRegex(ValueError,'No sketches'):picker.validate_sketches([])
        with TemporaryDirectory() as directory:
            first=Path(directory)/'first.ino';first.write_text('void setup() {}\nvoid loop() {}')
            picker.validate_sketches([str(first)])
            with self.assertRaisesRegex(ValueError,'Sketch not found'):
                picker.validate_sketches([str(first),str(Path(directory)/'missing.ino')])

    def test_existing_capture_command_accepts_step_output_folder(self):
        command=capture_command(dict(port='COM18',name='test_step001',out='results/queue_test/step_001'))
        self.assertEqual(command[command.index('--out')+1],'results/queue_test/step_001')

    def test_existing_hil_api_forwards_step_output_without_a_queue_worker(self):
        api=DesktopApi(Mock());api._capture=Mock();api._meter_power=Mock()
        api._capture.status.return_value=dict(running=False)
        config=gui_configuration();config['out']='results/queue_test/step_001'
        api.start_hil(config)
        command=api._capture.start.call_args.kwargs['command']
        self.assertEqual(command[3],'automation.backend.hil_worker')
        self.assertEqual(command[-2:],['--out',config['out']])
