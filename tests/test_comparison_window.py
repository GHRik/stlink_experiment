"""Exercise native Matplotlib interactions without measurement hardware."""
import json
import io
import gc
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import tkinter as tk
import unittest
from unittest.mock import patch
from matplotlib.colors import to_hex

from matplotlib.backend_bases import MouseEvent, KeyEvent

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
                native.geometry('900x650'); native.deiconify(); native.update_idletasks()
                region = window.viewport.bbox('all')
                self.assertGreater(region[2], window.viewport.winfo_width())
                self.assertGreater(region[3], window.viewport.winfo_height())
                window.viewport.yview_moveto(1)
                self.assertGreater(window.viewport.yview()[0], 0)
                window.viewport.xview_moveto(1)
                self.assertGreater(window.viewport.xview()[0], 0)
                window.viewport.yview_moveto(0); window.viewport.xview_moveto(0)
                native.withdraw()
                window.canvas.draw()
                left, right = window.plot.axes
                for ax in (left, right):
                    self.assertEqual([text.get_text().split(' | ')[0] for text in window.figure.legends[0].get_texts()], ['S1 · DUT1', 'S2 · DUT2'])
                label = window.figure.legends[0].get_texts()[0].get_text()
                self.assertNotIn('\n', label)
                for value in ('Repeats: 2', 'Duration: 2 s', 'Voltage: 3.3 V', 'Mean: 12.0000 mA', 'SD: 2.8284 mA', 'Mean energy: 0.079200 J'):
                    self.assertIn(value, label)
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
                    self.assertEqual([text.get_text().split(' | ')[0] for text in window.figure.legends[0].get_texts()], ['S1 · DUT1'])
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
                window.canvas.callbacks.process('key_press_event', KeyEvent('key_press_event', window.canvas, key='escape'))
                self.assertFalse(window.cursor.selections)
                self.assertIsNone(selection.annotation.axes)
                self.assertIsNotNone(window.cursor.select_at(line, (x, y)))
                window.canvas.callbacks.process('button_press_event', MouseEvent('button_press_event', window.canvas, 5, 5, button=3))
                self.assertFalse(window.cursor.selections)
                # Selecting a point still works after dismissing the previous one.
                self.assertIsNotNone(window.cursor.select_at(line, (x, y)))
                blank_x, blank_y = left.transData.transform((1.8, 12))
                window.canvas.callbacks.process('button_press_event', MouseEvent('button_press_event', window.canvas, blank_x, blank_y, button=1))
                self.assertFalse(window.cursor.selections)
                point_x, point_y = left.transData.transform((x, y))
                window.canvas.callbacks.process('button_press_event', MouseEvent('button_press_event', window.canvas, point_x, point_y, button=1))
                self.assertTrue(window.cursor.selections)
                # Use the actual repeat-menu command, not just the Python toggle method.
                menu_button = window.sessions.grid_slaves(row=0, column=1)[0]
                menu = menu_button.nametowidget(menu_button.cget('menu'))
                menu.invoke(3)
                native.update_idletasks()
                self.assertTrue(menu.winfo_exists())
                self.assertIs(window.repeat_buttons['S1'], menu_button)
                self.assertFalse(window.selection_vars[('S1', 'repeat_001')].get())
                self.assertEqual(window.selected_result['rows'][0]['mean_mA'], 14)
                self.assertIsNone(window.selected_result['rows'][0]['sd_mA'])
                self.assertEqual(window.selected_result['rows'][0]['repeats'], 1)
                self.assertTrue(all('repeat_001' not in label for _, label, _ in window.plot.targets))
                self.assertTrue(window.figure.legends[0].get_texts()[0].get_text().startswith('S1 · DUT1 | Repeats: 1 |'))
                # Reuse the same menu repeatedly, including the zero-repeat case.
                for index in (4, 3):
                    menu.invoke(index)
                    native.update_idletasks()
                    self.assertTrue(menu.winfo_exists())
                self.assertEqual(window.selected_result['rows'][0]['values'], [10])
                menu.invoke(3); native.update_idletasks()
                menu.invoke(4); native.update_idletasks()
                self.assertEqual(window.selected_result['rows'][0]['values'], [14])
                self.assertEqual(menu.entrycget(0, 'label'), 'Uncheck all')
                self.assertEqual(menu.entrycget(1, 'label'), 'Check all')
                menu.invoke(0); native.update_idletasks()
                self.assertEqual(window.selected_result['rows'][0]['repeats'], 0)
                self.assertFalse(any(window.selection_vars[('S1', name)].get() for name in ('repeat_001','repeat_002')))
                self.assertEqual(window.result['rows'][0]['repeats'], 2)
                menu.invoke(1); native.update_idletasks()
                self.assertEqual(window.selected_result['rows'][0]['values'], [10,14])
                self.assertAlmostEqual(window.selected_result['rows'][0]['sd_mA'], 8**.5)
                self.assertTrue(all(window.selection_vars[('S1', name)].get() for name in ('repeat_001','repeat_002')))
                self.assertIn('S2', window.hidden)
                self.assertTrue(menu.winfo_exists())
                menu.invoke(3); native.update_idletasks()
                # Apply range must update raw statistics asynchronously, retaining hidden sessions.
                window.begin.set('.5'); window.end.set('1.5'); window.apply()
                self.assertTrue(window.busy)
                self.assertIs(window.progress.master, native.pack_slaves()[0])
                self.assertIs(window.progress.master.pack_slaves()[-1], window.progress)
                self.assertEqual(window.table.heading('energy', 'text'), 'Mean energy [J]')
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
                    self.assertIn('Deep sleep reference', window.figure.legends[0].get_texts()[0].get_text())
                self.assertEqual(window.result['rows'][0]['name'], 'DUT1')
                self.assertEqual(window.selected_result['rows'][0]['name'], 'DUT1')
                self.assertTrue(all('Deep sleep reference' in label for _, label, _ in window.plot.targets))
                with TemporaryDirectory() as destination:
                    exported = window.plot.save(destination)
                    for filename in ('comparison_traces.svg', 'comparison_statistics.svg'):
                        self.assertIn('Deep sleep reference', (exported/filename).read_text(encoding='utf-8'))
                        self.assertIn('Repeats: 1 | Duration: 1 s | Voltage: 3.3 V | Mean: 14.0000 mA | SD: N/A (n&lt;2) | Mean energy: 0.046200 J',
                                      (exported/filename).read_text(encoding='utf-8').replace('n<2', 'n&lt;2'))
                    summary = json.loads((exported/'summary.json').read_text())
                    self.assertEqual(summary[0]['name'], 'DUT1')
                    self.assertEqual(summary[0]['display_name'], 'Deep sleep reference')
                def click_heading(column):
                    native.tk.call(window.table.heading(column, 'command'))
                click_heading('mean')
                self.assertEqual(window.table.get_children(), ('S1', 'S2'))
                self.assertTrue(window.table.heading('mean', 'text').endswith('▲'))
                click_heading('mean')
                self.assertEqual(window.table.get_children(), ('S2', 'S1'))
                self.assertTrue(window.table.heading('mean', 'text').endswith('▼'))
                window.render(keep_time=True)
                self.assertEqual(window.table.get_children(), ('S2', 'S1'))
                for _ in range(2):
                    click_heading('sd')
                    self.assertEqual(window.table.get_children(), ('S2', 'S1'))
                click_heading('session')
                self.assertEqual(window.table.get_children(), ('S1', 'S2'))
                click_heading('session')
                self.assertEqual(window.table.get_children(), ('S2', 'S1'))
                window.toggle_repeat('S1', 'repeat_001')
                self.assertEqual(window.name_vars['S1'].get(), 'Deep sleep reference')
                limits = [(ax.get_xlim(), ax.get_ylim()) for ax in window.plot.axes]
                window.sessions.grid_slaves(row=0, column=5)[0].invoke()
                self.assertEqual(window.name_vars['S1'].get(), 'DUT1')
                self.assertEqual(window.selected_result['rows'][0]['display_name'], 'DUT1')
                self.assertEqual([(ax.get_xlim(), ax.get_ylim()) for ax in window.plot.axes], limits)
                self.assertTrue(window.figure.legends[0].get_texts()[0].get_text().startswith('S1 · DUT1 |'))
                original_color = window.result['rows'][0]['color'][:]
                with patch('tkinter.colorchooser.askcolor', return_value=((18, 52, 86), '#123456')):
                    window.sessions.grid_slaves(row=0, column=6)[0].invoke()
                self.assertEqual(window.swatches['S1'].get(0, 0), (18, 52, 86))
                self.assertEqual(tuple(window.table.item('S1', 'image')), (str(window.swatches['S1']),))
                self.assertEqual(window.result['rows'][0]['color'], original_color)
                self.assertEqual([(ax.get_xlim(), ax.get_ylim()) for ax in window.plot.axes], limits)
                for line, label, _ in window.plot.targets:
                    if label.startswith('DUT1\n'): self.assertEqual(to_hex(line.get_color()), '#123456')
                self.assertEqual(to_hex(window.selected_result['rows'][0]['color']), '#123456')
                with TemporaryDirectory() as destination:
                    exported = window.plot.save(destination)
                    for filename in ('comparison_traces.svg', 'comparison_statistics.svg'):
                        self.assertIn('#123456', (exported/filename).read_text(encoding='utf-8'))
                    self.assertEqual(to_hex(json.loads((exported/'summary.json').read_text())[0]['color']), '#123456')
                window.toggle_repeat('S1', 'repeat_001')
                self.assertEqual(window.swatches['S1'].get(0, 0), (18, 52, 86))
                window.close(); window.poll()
                self.assertTrue(window.data._closed)
            finally:
                try: native.destroy()
                except tk.TclError: pass
