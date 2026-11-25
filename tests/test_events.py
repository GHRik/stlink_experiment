"""Exercise telemetry from measurement and HIL subprocesses through GUI polling."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from automation.backend.capture import CaptureProcess
from automation.HIL.run import Hardware
from src.events import emit
from src.stlink_protocol import Device


class EventTests(unittest.TestCase):
    def test_power_events_require_acknowledgement(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, STLINK_GUI_EVENT_FILE=str(Path(folder) / 'events')):
            device = Device.__new__(Device)
            device.events = []
            device.send = Mock()
            device.line = Mock(return_value=b'ack pwr off\r\n')
            device.command('pwr off')
            device.line.return_value = b'error pwr\r\n'
            with self.assertRaises(RuntimeError):
                device.command('pwr vout on')
            events = [json.loads(line) for line in (Path(folder) / 'events').read_text().splitlines()]
            self.assertEqual([(event['type'], event['enabled']) for event in events], [('meter_power', False)])

    def test_gui_receives_subprocess_events_even_when_stdout_is_silent(self):
        script = """from src.events import emit
import time
emit('hub', serial='TEST', port=3, enabled=True)
time.sleep(2)
emit('relay', channel=2, enabled=False)
"""
        runner = CaptureProcess()
        runner.start({}, command=[sys.executable, '-u', '-c', script])
        try:
            deadline = time.monotonic() + 5
            first = runner.status()
            while not first['events'] and time.monotonic() < deadline:
                time.sleep(.02)
                first = runner.status()
            self.assertTrue(first['running'])
            self.assertEqual(first['events'][0]['type'], 'hub')
            runner._thread.join(timeout=10)
            result = runner.status()
            self.assertEqual(result['returncode'], 0)
            self.assertEqual([event['type'] for event in result['events']], ['hub', 'relay'])
            self.assertEqual(result['lines'], [])
            self.assertEqual(runner.status(result['cursor'])['events'], [])
            self.assertEqual([event['type'] for event in runner.status(first['cursor'])['events']], ['relay'])
        finally:
            runner.close()

    def test_partial_event_is_not_consumed_until_its_newline_arrives(self):
        with tempfile.TemporaryDirectory() as folder:
            runner = CaptureProcess()
            runner._event_file = Path(folder) / 'events'
            runner._event_file.write_bytes(b'{"type":"meter_power","enabled":true}')
            self.assertEqual(runner.status()['events'], [])
            with runner._event_file.open('ab') as file:
                file.write(b'\n')
            self.assertTrue(runner.status()['events'][0]['enabled'])

    def test_hil_emits_physical_mapping_only_after_successful_switch(self):
        hardware = Hardware.__new__(Hardware)
        hardware.config = {'hub': {'serial': 'TEST'}}
        hardware.relays = Mock()
        hardware.hub = Mock()
        with patch('automation.HIL.run.emit') as event:
            hardware.relay(3, True)
            hardware.usb(2, False)
            self.assertEqual(event.call_args_list[0].kwargs, {'channel': 3, 'enabled': True})
            self.assertEqual(event.call_args_list[1].kwargs, {'serial': 'TEST', 'port': 2, 'enabled': False})
            hardware.hub.set.side_effect = RuntimeError('USB failed')
            with self.assertRaises(RuntimeError):
                hardware.usb(2, True)
            self.assertEqual(event.call_count, 2)

    def test_capture_emits_calibration_and_repeat_completion_through_worker(self):
        script = """import argparse, tempfile
from unittest.mock import patch
from src import stlink_measure, stlink_protocol
from tests.test_stlink_measure import FakeDevice
from automation.backend import capture_worker

def measure():
    with tempfile.TemporaryDirectory() as folder:
        args = argparse.Namespace(seconds=.1, hz=100, name='test', voltage=3.3,
            off_seconds=1, notes='fake', repeats=1, out=folder, port='FAKE', warmup_seconds=0)
        device = FakeDevice([b'ack start\\r\\n'] + [b'1000-05\\r\\n'] * 10 + [b'end\\r\\n'])
        device.close = lambda: None
        with patch.object(stlink_measure, 'Device', return_value=device), \\
             patch.object(stlink_measure, 'identify_device', return_value={}), \\
             patch.object(stlink_measure, 'configure_device'), \\
             patch.object(stlink_measure, 'save_session_settings'), \\
             patch.object(stlink_measure, 'analyze_run'), \\
             patch.object(stlink_measure, 'report'), \\
             patch.object(stlink_protocol.time, 'sleep'):
            stlink_measure.run_experiment(args)
capture_worker.measure_main = measure
capture_worker.main()
"""
        runner = CaptureProcess()
        runner.start({}, command=[sys.executable, '-u', '-c', script])
        try:
            runner._thread.join(timeout=20)
            result = runner.status()
            self.assertEqual(result['returncode'], 0, result['lines'])
            events = result['events']
            phases = [(event['type'], event.get('state')) for event in events]
            self.assertIn(('calibration', 'completed'), phases)
            self.assertIn(('repeat', 'completed'), phases)
            self.assertIn(('report', 'completed'), phases)
            preview = next(event for event in events if event['type'] == 'current_samples')
            self.assertEqual(preview['repeat'], 1)
            self.assertAlmostEqual(preview['points'][0][1], 10)
            self.assertLess(phases.index(('calibration', 'completed')), phases.index(('repeat', 'started')))
        finally:
            runner.close()
