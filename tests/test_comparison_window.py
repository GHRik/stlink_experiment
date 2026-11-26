"""Exercise native Matplotlib interactions without measurement hardware."""
import json
import io
import gc
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import tkinter as tk
import unittest

from matplotlib.backend_bases import MouseEvent

from automation.backend.comparison import generate_comparison
from automation.backend.comparison_window import ComparisonWindow, create_root
from tests.test_comparison import session


class NativeComparisonTests(unittest.TestCase):
    def test_toolbar_zoom_visibility_hover_range_and_close(self):
        with TemporaryDirectory() as directory, TemporaryDirectory() as work:
            root = Path(directory)
            session(root, 'DUT1', [10, 14]); session(root, 'DUT2', [100, 104])
            generate_comparison(root, ['DUT1', 'DUT2'], work)
            native = create_root()
            native.withdraw()
            window = ComparisonWindow(native, work)
            try:
                window.canvas.draw()
                left, right = window.plot.axes
                for ax in (left, right):
                    self.assertEqual([text.get_text().splitlines()[0] for text in ax.get_legend().get_texts()], ['S1 · DUT1', 'S2 · DUT2'])
                original_xlim = left.get_xlim()
                window.toolbar.push_current()
                # Use Matplotlib's actual rectangle-zoom tool, not a custom drag handler.
                window.toolbar.zoom()
                for name, x, y in [('button_press_event', .4, 30), ('button_release_event', 1.2, 80)]:
                    px, py = left.transData.transform((x, y))
                    event = MouseEvent(name, window.canvas, px, py, button=1)
                    window.canvas.callbacks.process(name, event)
                self.assertLess(left.get_xlim()[1]-left.get_xlim()[0], original_xlim[1]-original_xlim[0])
                window.toolbar.home()
                self.assertEqual(left.get_xlim(), original_xlim)
                window.toolbar.zoom()
                # Scrolling zooms around the pointer and can be reversed.
                px, py = left.transData.transform((1, 50))
                window.scroll(MouseEvent('scroll_event', window.canvas, px, py, button='up'))
                self.assertLess(left.get_xlim()[1]-left.get_xlim()[0], 2)
                window.scroll(MouseEvent('scroll_event', window.canvas, px, py, button='down'))
                self.assertAlmostEqual(left.get_xlim()[1]-left.get_xlim()[0], 2)
                gc.collect()
                self.assertTrue(window.selection_vars[('S2', None)].get())
                checkbox = next(widget for widget in window.sessions.winfo_children()
                                if isinstance(widget, tk.Checkbutton) and widget.cget('text').startswith('S2'))
                checkbox.invoke()
                gc.collect()
                self.assertFalse(window.selection_vars[('S2', None)].get())
                left, right = window.plot.axes
                self.assertLess(left.get_ylim()[1], 20)
                self.assertLess(right.get_ylim()[1], 20)
                self.assertTrue(all('DUT2' not in label for _, label, _ in window.plot.targets))
                for ax in (left, right):
                    self.assertEqual([text.get_text().splitlines()[0] for text in ax.get_legend().get_texts()], ['S1 · DUT1'])
                # The standard Figure save path must include only currently visible session labels.
                saved = io.StringIO()
                window.figure.savefig(saved, format='svg')
                self.assertIn('S1 · DUT1', saved.getvalue())
                self.assertNotIn('S2 · DUT2', saved.getvalue())
                # Hover readout includes repeat identity and measured value.
                window.canvas.draw()
                line, _, _ = window.plot.targets[0]
                x, y = line.get_xdata()[1], line.get_ydata()[1]
                px, py = left.transData.transform((x, y))
                selection = window.cursor.select_at(line, (x, y))
                self.assertIsNotNone(selection)
                self.assertIn('repeat_001', selection.annotation.get_text())
                self.assertIn('10.0000 mA', selection.annotation.get_text())
                # Use the actual repeat-menu command, not just the Python toggle method.
                menu_button = window.sessions.grid_slaves(row=0, column=1)[0]
                menu = menu_button.nametowidget(menu_button.cget('menu'))
                menu.invoke(0)
                native.update_idletasks()
                self.assertTrue(menu.winfo_exists())
                self.assertIs(window.repeat_buttons['S1'], menu_button)
                self.assertFalse(window.selection_vars[('S1', 'repeat_001')].get())
                self.assertEqual(window.selected_result['rows'][0]['mean_mA'], 14)
                self.assertIsNone(window.selected_result['rows'][0]['sd_mA'])
                self.assertEqual(window.selected_result['rows'][0]['repeats'], 1)
                self.assertTrue(all('repeat_001' not in label for _, label, _ in window.plot.targets))
                self.assertEqual('S1 · DUT1', window.plot.axes[0].get_legend().get_texts()[0].get_text())
                # Reuse the same menu repeatedly, including the zero-repeat case.
                for index in (1, 0):
                    menu.invoke(index)
                    native.update_idletasks()
                    self.assertTrue(menu.winfo_exists())
                self.assertEqual(window.selected_result['rows'][0]['values'], [10])
                menu.invoke(0); native.update_idletasks()
                menu.invoke(1); native.update_idletasks()
                self.assertEqual(window.selected_result['rows'][0]['values'], [14])
                # Apply range must update raw statistics asynchronously, retaining hidden sessions.
                window.begin.set('.5'); window.end.set('1.5'); window.apply()
                self.assertTrue(window.busy)
                deadline = time.monotonic()+30
                while window.busy and time.monotonic()<deadline:
                    native.update(); time.sleep(.02)
                self.assertFalse(window.busy)
                self.assertEqual(window.result['rows'][0]['seconds'], 1)
                self.assertIn('S2', window.hidden)
                self.assertEqual(window.selected_result['rows'][0]['mean_mA'], 14)
                self.assertEqual(window.selected_result['rows'][0]['repeats'], 1)
                self.assertEqual(json.loads((Path(work)/'preview.json').read_text())['analysis_range'], [.5, 1.5])
                self.assertFalse(list(Path(work).rglob('*.png')))
                self.assertFalse(list(Path(work).rglob('*.svg')))
                # Renaming affects labels and exports while preserving zoom and source identity.
                window.plot.axes[0].set_xlim(.6, 1.1)
                window.plot.axes[1].set_ylim(12, 16)
                window.name_vars['S1'].set('Deep sleep reference')
                window.sessions.grid_slaves(row=0, column=4)[0].invoke()
                self.assertEqual(window.plot.axes[0].get_xlim(), (.6, 1.1))
                self.assertEqual(window.plot.axes[1].get_ylim(), (12, 16))
                for ax in window.plot.axes:
                    self.assertIn('Deep sleep reference', ax.get_legend().get_texts()[0].get_text())
                self.assertEqual(window.result['rows'][0]['name'], 'DUT1')
                self.assertEqual(window.selected_result['rows'][0]['name'], 'DUT1')
                self.assertTrue(all('Deep sleep reference' in label for _, label, _ in window.plot.targets))
                with TemporaryDirectory() as destination:
                    exported = window.plot.save(destination)
                    for filename in ('comparison_traces.svg', 'comparison_statistics.svg'):
                        self.assertIn('Deep sleep reference', (exported/filename).read_text(encoding='utf-8'))
                    summary = json.loads((exported/'summary.json').read_text())
                    self.assertEqual(summary[0]['name'], 'DUT1')
                    self.assertEqual(summary[0]['display_name'], 'Deep sleep reference')
                window.toggle_repeat('S1', 'repeat_001')
                self.assertEqual(window.name_vars['S1'].get(), 'Deep sleep reference')
                window.close(); window.poll()
                self.assertTrue(window.data._closed)
            finally:
                try: native.destroy()
                except tk.TclError: pass
