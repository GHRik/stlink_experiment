import argparse
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import stlink_protocol as app
import results
import stlink_measure


class FakeDevice:
    def __init__(self, lines):
        self.lines = iter(lines)
        self.events = []

    def command(self, command, timeout=5):
        self.events.append({"tx": command})
        if command == "temp degc refresh":
            return "ack temp degc refresh: 27.5"
        if command == "status":
            return "ack status ok"
        return "ack " + command

    def send(self, command):
        self.events.append({"tx": command})

    def drain(self, seconds):
        pass

    def line(self):
        return next(self.lines, b"end\r\n")


class Tests(unittest.TestCase):
    def test_temperature_command_ignores_late_stop_ack(self):
        device = app.Device.__new__(app.Device)
        device.events = []
        lines = iter([b"ack stop\r\n", b"ack temp degc refresh 35.0\r\n"])
        device.line = lambda: next(lines)
        with patch.object(device, "send"):
            self.assertEqual(app.read_temperature(device), 35.0)

    def test_capture_reports_only_its_named_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = argparse.Namespace(seconds=0.1, hz=100, name="modem", voltage=3.3,
                                      off_seconds=1, notes="test", repeats=2,
                                      out=temporary, port="FAKE")
            with patch.object(stlink_measure, "Device") as device, \
                 patch.object(stlink_measure, "identify_device", return_value={}), \
                 patch.object(stlink_measure, "configure_device"), \
                 patch.object(stlink_measure, "save_session_settings"), \
                 patch.object(stlink_measure, "warm_up", return_value={}), \
                 patch.object(stlink_measure, "capture_one") as capture, \
                 patch.object(stlink_measure, "analyze_run"), \
                 patch.object(stlink_measure, "report") as report:
                device.return_value.events = []
                stlink_measure.run_experiment(args)
            folders = list(Path(temporary).iterdir())
            self.assertEqual(len(folders), 1)
            self.assertRegex(folders[0].name, r"^modem_\d{8}_\d{6}_\d{6}$")
            report.assert_called_once_with(folders[0], begin=0, end=None)
            self.assertEqual([call.args[1].name for call in capture.call_args_list],
                             ["repeat_001", "repeat_002"])

    def test_warmup_turns_power_off_on_interruption(self):
        device = FakeDevice([])
        with patch.object(app.time, "sleep", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                app.warm_up(device, 180)
        self.assertEqual(device.events[-1]["tx"], "pwr off")

    def test_temperature_and_calibration_before_capture(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "repeat"
            device = self.capture(path, [b"ack start\r\n"] +
                                  [b"1000-05\r\n"] * 10 + [b"end\r\n"])
            commands = [event["tx"] for event in device.events]
            self.assertLess(commands.index("calib"), commands.index("status"))
            self.assertLess(commands.index("pwr vout on"), commands.index("calib"))
            self.assertIn("pwr off", commands[commands.index("calib") + 1:commands.index("start")])
            self.assertLess(commands.index("status"), commands.index("start"))
            self.assertEqual(commands[-1], "temp degc refresh")
            meta = json.loads((path / "metadata.json").read_text())
            self.assertEqual(meta["temperature_before_C"], 27.5)
            self.assertEqual(meta["temperature_after_C"], 27.5)
            self.assertEqual(meta["calibration"]["status"], "acknowledged")

    def test_calibration_failure_prevents_acquisition(self):
        with tempfile.TemporaryDirectory() as temporary:
            device = FakeDevice([])
            original = device.command
            device.command = lambda command, **kw: "ack status error" if command == "status" else original(command, **kw)
            args = argparse.Namespace(seconds=0.1, hz=100, name="test", voltage=3.3,
                                      off_seconds=1, notes="fake")
            path = Path(temporary) / "repeat"
            with self.assertRaises(RuntimeError):
                app.capture_one(device, path, args, {}, 1)
            self.assertNotIn("start", [event["tx"] for event in device.events])
            self.assertEqual(json.loads((path / "metadata.json").read_text())["status"], "invalid")

    def test_bilingual_reports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.capture(root / "repeat_001", [b"ack start\r\n"] +
                         [b"1000-05\r\n"] * 10 + [b"end\r\n"])
            results.report(root, 0, None)
            for language, phrase in (("pl", "Powtórzenie 1"),
                                     ("eng", "Repeat 1")):
                for base in ("comparison", "statistics"):
                    for extension in ("png", "svg"):
                        self.assertTrue((root / f"{base}_{language}.{extension}").exists())
                self.assertIn(phrase, (root / f"statistics_{language}.svg").read_text(encoding="utf-8"))

    def test_report_layout_for_long_captures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for count in (5, 10):
                rows, runs = [], []
                for number in range(count):
                    data = np.zeros(1001, dtype=[("time_s", float), ("current_uA", float)])
                    data["time_s"] = np.linspace(0, 1000, len(data))
                    data["current_uA"] = 20000 + number * 100
                    row = dict(configuration="modem", voltage_V=3.3, sampling_Hz=1,
                               begin_s=0, end_s=1000, conditions="same",
                               mean_current_mA=20 + number * 0.1,
                               energy_estimate_J=(20 + number * 0.1) * 3.3)
                    rows.append(row)
                    runs.append((row, data))
                def check_layout(fig, base, bottom=0):
                    fig.tight_layout(rect=(0, bottom, 1, 1))
                    fig.canvas.draw()
                    renderer = fig.canvas.get_renderer()
                    legend = fig.legends[0].get_window_extent(renderer)
                    footer = fig.texts[-1].get_window_extent(renderer)
                    self.assertLess(footer.y1, legend.y0)
                    self.assertLess(legend.y1, min(ax.get_tightbbox(renderer).y0 for ax in fig.axes))
                    for box in (legend, footer):
                        self.assertGreaterEqual(box.x0, 0)
                        self.assertLessEqual(box.x1, fig.bbox.width)
                    if base.name.startswith("comparison"):
                        self.assertGreater(fig.axes[0].get_xlim()[1], 1000)
                        self.assertEqual(len(fig.axes), 2)
                        self.assertEqual(fig.axes[1].get_xlim(), (0, 1))
                        self.assertEqual(len(fig.axes[1].lines), count)
                    results.plt.close(fig)
                for language in ("pl", "eng"):
                    with patch.object(results, "plot_save", side_effect=check_layout) as save:
                        results.plot_report(root, rows, {"modem": runs}, results.aggregate(rows), language)
                    self.assertEqual(save.call_count, 2)

    def test_startup_zoom_preserves_raw_peak_and_absolute_time(self):
        fig, (overview, zoom) = results.plt.subplots(1, 2)
        times = np.array([0, 0.001, 0.002, 0.999, 1.0, 2.0])
        current = np.array([20, 155, 75, 74, 200, 73])
        overview.plot(times, current)
        peak = results.startup_trace(overview, zoom, times, current)
        results.finish_startup(overview, zoom, [peak])
        np.testing.assert_array_equal(zoom.lines[0].get_ydata(), current[:4])
        self.assertEqual(peak[:2], (0.001, 155))
        self.assertIn("155.000 mA", zoom.texts[0].get_text())
        results.plt.close(fig)
        fig, (overview, zoom) = results.plt.subplots(1, 2)
        peak = results.startup_trace(overview, zoom, times[-2:], current[-2:])
        results.finish_startup(overview, zoom, [peak])
        self.assertIsNone(peak)
        self.assertEqual(len(zoom.lines), 0)
        self.assertIn("Outside", zoom.texts[0].get_text())
        results.plt.close(fig)

    def test_real_firmware_prompt_before_ack(self):
        class Serial:
            def write(self, data):
                self.command = data
            def flush(self):
                pass
        device = app.Device.__new__(app.Device)
        device.serial = Serial()
        device.events = []
        device.line = lambda: b"stlp > ack version: V3PWR V4.J7.B3.P6\r\n"
        self.assertEqual(device.command("version"), "ack version: V3PWR V4.J7.B3.P6")
        self.assertEqual(device.serial.command, b"version\r\n")
        self.assertEqual(app.normalize_line("stlp >"), "")
        self.assertAlmostEqual(app.decode_sample("stlp > 6409-07"), 640.9e-6)

    def test_capture_with_prompt_prefixed_lines(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run"
            self.capture(path, [b"stlp > ack start\r\n", b"stlp >\r\n"] +
                         [b"stlp > 1000-05\r\n"] * 10 + [b"stlp > end\r\n"])
            row, _ = results.analyze_run(path, 0, None)
            self.assertAlmostEqual(row["mean_current_mA"], 10)

    def test_serial_fragmented_lines_and_crlf(self):
        class Serial:
            in_waiting = 1
            def __init__(self):
                self.chunks = iter([b"ack ", b"start\r", b"\n6409-", b"07\r\n"])
                self.written = b""
            def read(self, size):
                return next(self.chunks, b"")
            def write(self, data):
                self.written += data
            def flush(self):
                pass
        device = app.Device.__new__(app.Device)
        device.serial = Serial()
        device.pending = bytearray()
        device.events = []
        device.send("start")
        self.assertEqual(device.serial.written, b"start\r\n")
        self.assertEqual(device.line(), b"ack start\r\n")
        self.assertEqual(device.line(), b"6409-07\r\n")

    def test_protocol_units(self):
        self.assertAlmostEqual(app.decode_sample("6409-07"), 640.9e-6)
        self.assertAlmostEqual(app.decode_sample("1000-05"), 0.01)
        self.assertAlmostEqual(app.decode_sample("0000-09"), 0)
        self.assertIsNone(app.decode_sample("RecID 12"))
        self.assertIsNone(app.decode_sample("ack start"))
        self.assertIsNone(app.decode_sample("not a sample"))

    def capture(self, path, lines):
        args = argparse.Namespace(seconds=0.1, hz=100, name="test", voltage=3.3,
                                  off_seconds=1, notes="fake")
        device = FakeDevice(lines)
        with patch.object(app.time, "sleep"):
            app.capture_one(device, path, args, {"whoami": "SIMULATED"}, 1)
        return device

    def test_capture_known_current_and_exact_window(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run"
            device = self.capture(path, [b"ack start\r\n"] +
                                  [b"1000-05\r\n"] * 12 + [b"end\r\n"])
            row, data = results.analyze_run(path, 0, None)
            self.assertEqual(len(data), 10)  # additional transport samples excluded
            self.assertAlmostEqual(row["mean_current_mA"], 10)
            self.assertAlmostEqual(row["energy_estimate_J"], 0.0033)
            self.assertTrue((path / "current.png").exists())
            commands = [e["tx"] for e in device.events]
            self.assertLess(commands.index("pwr off"), commands.index("start"))
            self.assertIn("stop", commands)
            row, _ = results.analyze_run(path, 0.02, 0.07)
            self.assertEqual(row["samples"], 5)
            self.assertAlmostEqual(row["energy_estimate_J"], 0.00165)

    def test_resynchronization_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run"
            with self.assertRaises(RuntimeError):
                self.capture(path, [b"ack start\r\n", b"1000-05\r\n",
                                    b"RecID 5\r\n"] + [b"1000-05\r\n"] * 9 + [b"end\r\n"])
            meta = json.loads((path / "metadata.json").read_text())
            self.assertEqual(meta["status"], "invalid")
            with self.assertRaises(ValueError):
                results.load_run(path)

    def test_short_stream_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run"
            with self.assertRaises(RuntimeError):
                self.capture(path, [b"ack start\r\n", b"1000-05\r\n", b"end\r\n"])
            self.assertEqual(json.loads((path / "metadata.json").read_text())["status"], "invalid")

    def test_real_calibration_messages_excluded(self):
        for messages in ([b"RecID: 57777 after Calib\r\n"],
                         [b"warning: An automatic calibration has been done\r\n"],
                         [b"RecID: 57777 after Calib\r\n",
                          b"warning: An automatic calibration has been done\r\n"]):
            with self.subTest(messages=messages), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "repeat"
                with self.assertRaises(RuntimeError):
                    self.capture(path, [b"ack start\r\n", b"1000-05\r\n"] +
                                 messages + [b"1000-05\r\n"] * 9 + [b"end\r\n"])
                meta = json.loads((path / "metadata.json").read_text())
                self.assertEqual(meta["status"], "invalid")
                self.assertTrue(all("repeat this measurement" in issue for issue in meta["issues"]))
                self.assertTrue((path / "stream.bin").exists())

    def test_between_run_sd_not_within_run_sd(self):
        rows = []
        for value in (1, 2, 3):
            rows.append(dict(configuration="test", voltage_V=3.3, sampling_Hz=100,
                             begin_s=0, end_s=10, conditions="same",
                             mean_current_mA=value, energy_estimate_J=value * 0.033))
        result = results.aggregate(rows)[0]
        self.assertAlmostEqual(result["mean_current_mA_mean"], 2)
        self.assertAlmostEqual(result["mean_current_mA_between_run_sd"], 1)
        self.assertLess(result["mean_current_mA_ci95_low"], 2)
        self.assertGreater(result["mean_current_mA_ci95_high"], 2)
        self.assertIsNone(results.aggregate(rows[:1])[0]["mean_current_mA_between_run_sd"])
        rows[0]["voltage_V"] = 3.2
        self.assertEqual(len(results.aggregate(rows)), 2)


if __name__ == "__main__":
    unittest.main()
