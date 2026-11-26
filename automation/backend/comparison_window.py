"""Native Matplotlib comparison window; launched separately from pywebview."""
from datetime import datetime
import json
import os
from pathlib import Path
from queue import Queue, Empty
import sys
from threading import Thread
from types import SimpleNamespace

import numpy as np
from matplotlib.figure import Figure

from .comparison import ComparisonData


def select_repeats(result, excluded):
    """Reaggregate cached full-resolution repeat statistics, never preview bins."""
    rows = []
    for source in result['rows']:
        indices = [i for i, name in enumerate(source['repeat_names']) if (source['id'], name) not in excluded]
        values = [source['values'][i] for i in indices]
        energies = [source['repeat_energies_J'][i] for i in indices]
        rows.append({**source, 'repeats': len(indices), 'values': values,
            'repeat_names': [source['repeat_names'][i] for i in indices],
            'repeat_energies_J': energies,
            'omitted_repeats': [name for name in source['repeat_names'] if (source['id'], name) in excluded],
            'mean_mA': float(np.mean(values)) if values else None,
            'sd_mA': float(np.std(values, ddof=1)) if len(values) > 1 else None,
            'energy_J': float(np.mean(energies)) if energies else None})
    return dict(rows=rows, preview={**result['preview'], 'series': [series for series in result['preview']['series']
                if (series['id'], series['repeat']) not in excluded]})


def legend_label(row):
    name = ' '.join(row.get('display_name', row['name']).split())
    sd = 'N/A (n<2)' if row['sd_mA'] is None else f"{row['sd_mA']:.4f} mA"
    return (f"{row['id']} · {name} | Repeats: {row['repeats']} | Duration: {row['seconds']:g} s"
            f" | Voltage: {row['voltage']:g} V | Mean: {row['mean_mA']:.4f} mA"
            f" | SD: {sd} | Mean energy: {row['energy_J']:.6f} J")


class ComparisonFigure:
    """Matplotlib artists shared by the desktop view and explicit exports."""

    def __init__(self, figure, result, hidden=()):
        self.figure, self.result, self.hidden = figure, result, set(hidden)
        self.axes = figure.subplots(1, 2)
        self.targets = []
        self.draw()

    def draw(self, limits=None):
        for legend in list(self.figure.legends): legend.remove()
        self.targets.clear()
        left, right = self.axes
        for ax in self.axes:
            ax.clear()
            ax.grid(alpha=.25)
            ax.ticklabel_format(axis='y', style='plain', useOffset=False)
        for series in self.result['preview']['series']:
            if series['id'] in self.hidden:
                continue
            points = np.asarray(series['points'])
            line, = left.plot(points[:, 0], points[:, 1], color=series['color'], alpha=.7, linewidth=.8)
            left.fill_between(points[:, 0], points[:, 2], points[:, 3], color=series['color'], alpha=.12)
            self.targets.append((line, f"{series.get('display_name', series['name'])}\n{series['id']} · {series['repeat']}", 'trace'))
        for index, row in enumerate(self.result['rows']):
            if row['id'] in self.hidden or not row['repeats']:
                continue
            offsets = np.linspace(-.15, .15, row['repeats']) if row['repeats'] > 1 else [0]
            # Separate artists make each repeat available to Matplotlib's hit testing.
            for offset, value, repeat in zip(offsets, row['values'], row['repeat_names']):
                dot, = right.plot(index+offset, value, 'o', color=row['color'], markersize=4)
                self.targets.append((dot, f"{row.get('display_name', row['name'])}\n{row['id']} · {repeat}", 'repeat'))
            bars = right.errorbar(index, row['mean_mA'], yerr=row['sd_mA'], fmt='o',
                color=row['color'], markeredgecolor='black', markersize=8, capsize=6)
            sd = 'N/A (n=1)' if row['sd_mA'] is None else f"{row['sd_mA']:.4f} mA"
            self.targets.append((bars.lines[0], f"{row.get('display_name', row['name'])}\n{row['id']} · Session mean\nSD: {sd}", 'mean'))
        left.set(xlabel='Time [s]', ylabel='Current [mA]', title='Current traces')
        left.set_xlim(*self.result['preview']['bounds'])
        right.set(xlabel='Session', ylabel='Mean current [mA]', title='Mean current ± sample SD')
        right.set_xticks(range(len(self.result['rows'])), [row['id'] for row in self.result['rows']])
        right.set_xlim(-.5, max(.5, len(self.result['rows'])-.5))
        if limits:
            for ax, (xlim, ylim) in zip(self.axes, limits):
                ax.set_xlim(*xlim)
                ax.set_ylim(*ylim)
        else:
            self.fit_trace_y()
        from matplotlib.lines import Line2D
        handles = [Line2D([], [], color=row['color'], label=legend_label(row))
                   for row in self.result['rows'] if row['id'] not in self.hidden and row['repeats']]
        if handles:
            self.figure.legend(handles=handles, loc='outside lower center', fontsize=8, frameon=False)

    def fit_trace_y(self):
        low, high = self.axes[0].get_xlim()
        extremes = []
        for series in self.result['preview']['series']:
            if series['id'] in self.hidden:
                continue
            points = np.asarray(series['points'])
            # Include neighboring bin centers to cover the visible line segments.
            first = max(0, np.searchsorted(points[:, 0], low)-1)
            last = min(len(points), np.searchsorted(points[:, 0], high)+1)
            if last > first:
                extremes.extend([points[first:last, 2].min(), points[first:last, 3].max()])
        if extremes:
            minimum, maximum = min(extremes), max(extremes)
            pad = max((maximum-minimum)*.08, abs(maximum)*.001, 1e-6)
            self.axes[0].set_ylim(minimum-pad, maximum+pad)

    def attach_cursor(self):
        import mplcursors
        labels = {line: (label, kind) for line, label, kind in self.targets}
        cursor = mplcursors.cursor(list(labels), highlight=True)
        @cursor.connect('add')
        def describe(selection):
            label, kind = labels[selection.artist]
            x, y = selection.target
            value = f'X: {x:.6f} s\nY: {y:.4f} mA (bin mean)' if kind == 'trace' else f'Mean: {y:.4f} mA'
            selection.annotation.set_text(f'{label}\n{value}')
        return cursor

    def save(self, destination):
        folder = Path(destination) / ('comparison_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        folder.mkdir()
        limits = [(ax.get_xlim(), ax.get_ylim()) for ax in self.axes]
        # Reuse the same artists and exact view limits without hover decorations.
        for index, base in enumerate(('comparison_traces', 'comparison_statistics')):
            export = Figure(figsize=(14, 6), layout='constrained')
            plots = ComparisonFigure(export, self.result, self.hidden)
            plots.draw(limits)
            export.delaxes(plots.axes[1-index])
            plots.axes[index].set_subplotspec(export.add_gridspec(1, 1)[0])
            for extension in ('png', 'svg'):
                export.savefig(folder / f'{base}.{extension}', bbox_inches='tight', dpi=180)
        rows = [{**row, 'visible': row['id'] not in self.hidden and bool(row['repeats'])} for row in self.result['rows']]
        (folder / 'summary.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
        (folder / 'view.json').write_text(json.dumps(dict(limits=limits, analysis_range=self.result['preview']['analysis_range'])), encoding='utf-8')
        return folder


class ComparisonWindow:
    def __init__(self, root, directory):
        import tkinter as tk
        from tkinter import ttk
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

        self.root, self.directory = root, Path(directory)
        self.data = ComparisonData(SimpleNamespace(name=str(directory), cleanup=lambda: None))
        self.result = self.data.get_comparison()
        self.hidden, self.busy, self.closing = set(), False, False
        self.excluded_repeats = set()
        self.selection_vars = {}
        self.repeat_buttons = {}
        self.display_names, self.name_vars = {}, {}
        self.cursor = None
        self.queue = Queue()
        root.title('Measurement comparison — Matplotlib Figure')
        root.geometry('1400x900'); root.minsize(900, 650)
        status_header = ttk.Frame(root)
        status_header.pack(fill='x')
        self.status = tk.StringVar(value='')
        ttk.Label(status_header, textvariable=self.status, font=('Segoe UI', 12)).pack(fill='x', padx=12)
        self.progress = ttk.Progressbar(status_header, mode='indeterminate')
        container = ttk.Frame(root); container.pack(fill='both', expand=True)
        container.rowconfigure(0, weight=1); container.columnconfigure(0, weight=1)
        self.viewport = tk.Canvas(container, highlightthickness=0)
        self.viewport.grid(row=0, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(container, orient='vertical', command=self.viewport.yview)
        horizontal = ttk.Scrollbar(container, orient='horizontal', command=self.viewport.xview)
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        self.viewport.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.body = ttk.Frame(self.viewport)
        self.body_item = self.viewport.create_window(0, 0, window=self.body, anchor='nw')
        self.body.bind('<Configure>', self.layout_scroll_area)
        self.viewport.bind('<Configure>', self.layout_scroll_area)
        root.bind('<MouseWheel>', self.scroll_window)
        controls = ttk.Frame(self.body, padding=8); controls.pack(fill='x')
        self.begin, self.end = tk.StringVar(), tk.StringVar()
        self.buttons, self.entries = [], []
        for label, variable in [('From [s]', self.begin), ('To [s]', self.end)]:
            ttk.Label(controls, text=label).pack(side='left', padx=4)
            entry = ttk.Entry(controls, textvariable=variable, width=10); entry.pack(side='left')
            self.entries.append(entry)
        for text, action in [('Apply range', self.apply), ('Use visible range', self.use_view),
                             ('Full range', lambda: self.apply(full=True)), ('Save figures…', self.save),
                             ('Export samples…', self.export)]:
            button = ttk.Button(controls, text=text, command=action); button.pack(side='left', padx=4)
            self.buttons.append(button)
        self.sessions = ttk.Frame(self.body, padding=8); self.sessions.pack(fill='x')
        self.figure = Figure(figsize=(14, 5), layout='constrained')
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.body)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.body, pack_toolbar=False)
        self.toolbar.pack(fill='x')
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        columns = ('session', 'n', 'duration', 'voltage', 'mean', 'sd', 'energy')
        self.table_sort = (None, False)
        self.table_headings = dict(zip(columns, ('Session', 'Repeats', 'Duration [s]', 'Voltage [V]', 'Mean [mA]', 'SD [mA]', 'Mean energy [J]')))
        self.table = ttk.Treeview(self.body, columns=columns, show='headings', height=4)
        for key, heading in self.table_headings.items():
            self.table.heading(key, text=heading, command=lambda key=key: self.sort_table(key))
            self.table.column(key, width=110 if key != 'session' else 400)
        self.table.pack(fill='x', padx=8, pady=8)
        self.canvas.mpl_connect('scroll_event', self.scroll)
        self.canvas.mpl_connect('key_press_event', self.dismiss_point)
        self.canvas.mpl_connect('button_press_event', self.dismiss_point)
        root.bind('<Escape>', lambda event: self.dismiss_point())
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.render()
        root.after(100, self.poll)

    def layout_scroll_area(self, event=None):
        self.viewport.itemconfigure(self.body_item,
            width=max(self.viewport.winfo_width(), self.body.winfo_reqwidth(), 1100),
            height=max(self.viewport.winfo_height(), self.body.winfo_reqheight()))
        self.viewport.configure(scrollregion=self.viewport.bbox('all'))

    def scroll_window(self, event):
        # Wheel over the Figure keeps its zoom behavior; elsewhere it scrolls the window.
        if str(event.widget).startswith(str(self.canvas.get_tk_widget())) or not event.delta: return
        self.viewport.yview_scroll((-1 if event.delta > 0 else 1) * max(1, abs(event.delta)//120), 'units')

    def render(self, keep_time=False, keep_limits=False):
        import tkinter as tk
        from tkinter import ttk
        time_view = self.plot.axes[0].get_xlim() if keep_time else None
        limits = [(ax.get_xlim(), ax.get_ylim()) for ax in self.plot.axes] if keep_limits else None
        if self.cursor: self.cursor.remove()
        self.figure.clear()
        self.selected_result = select_repeats(self.result, self.excluded_repeats)
        for row in self.selected_result['rows']:
            row['display_name'] = self.display_names.get(row['id'], row['name'])
        self.selected_result['preview']['series'] = [
            {**series, 'display_name': self.display_names.get(series['id'], series['name'])}
            for series in self.selected_result['preview']['series']]
        self.plot = ComparisonFigure(self.figure, self.selected_result, self.hidden)
        if limits:
            self.plot.draw(limits)
        elif time_view:
            self.plot.axes[0].set_xlim(*time_view); self.plot.fit_trace_y()
        self.toolbar.update()
        self.cursor = self.plot.attach_cursor()
        self.canvas.draw_idle()
        # Keep native menus alive while Windows finishes their selection callbacks.
        if not self.selection_vars:
            for index, row in enumerate(self.result['rows']):
                sid = row['id']
                variable = self.selection_vars[(sid, None)] = tk.BooleanVar(value=sid not in self.hidden)
                color = '#%02x%02x%02x' % tuple(round(c*255) for c in row['color'][:3])
                button = tk.Checkbutton(self.sessions, text=f"{row['id']} · {row['name']}", variable=variable,
                    foreground=color, anchor='w', command=lambda sid=row['id']: self.toggle(sid))
                button.grid(row=index, column=0, sticky='w', padx=5)
                count = sum((sid, name) not in self.excluded_repeats for name in row['repeat_names'])
                repeats = self.repeat_buttons[sid] = ttk.Menubutton(self.sessions, text=f'Repeats ({count}/{row["repeats"]})')
                menu = tk.Menu(repeats, tearoff=False)
                menu.add_command(label='Uncheck all',
                    command=lambda sid=sid: self.root.after_idle(self.set_all_repeats, sid, False))
                menu.add_command(label='Check all',
                    command=lambda sid=sid: self.root.after_idle(self.set_all_repeats, sid, True))
                menu.add_separator()
                repeats.configure(menu=menu)
                repeats.grid(row=index, column=1, sticky='w')
                for name in row['repeat_names']:
                    variable = self.selection_vars[(sid, name)] = tk.BooleanVar(value=(sid, name) not in self.excluded_repeats)
                    menu.add_checkbutton(label=name, variable=variable,
                        command=lambda sid=sid, name=name: self.root.after_idle(self.toggle_repeat, sid, name))
                ttk.Label(self.sessions, text='Legend name:').grid(row=index, column=2, padx=(12, 4))
                name_var = self.name_vars[sid] = tk.StringVar(value=self.display_names.get(sid, row['name']))
                entry = ttk.Entry(self.sessions, textvariable=name_var, width=32)
                entry.grid(row=index, column=3, sticky='ew')
                entry.bind('<Return>', lambda event, sid=sid: self.rename(sid))
                ttk.Button(self.sessions, text='Rename', command=lambda sid=sid: self.rename(sid)).grid(row=index, column=4, padx=4)
                ttk.Button(self.sessions, text='Reset to original', command=lambda sid=sid: self.reset_name(sid)).grid(row=index, column=5, padx=4)
        for row in self.result['rows']:
            sid = row['id']
            self.selection_vars[(sid, None)].set(sid not in self.hidden)
            for name in row['repeat_names']:
                self.selection_vars[(sid, name)].set((sid, name) not in self.excluded_repeats)
            count = sum((sid, name) not in self.excluded_repeats for name in row['repeat_names'])
            self.repeat_buttons[sid].configure(text=f'Repeats ({count}/{row["repeats"]})')
            self.name_vars[sid].set(self.display_names.get(sid, row['name']))
        self.table.delete(*self.table.get_children())
        for row in self.selected_result['rows']:
            self.table.insert('', 'end', iid=row['id'], values=(row['display_name'], row['repeats'], row['seconds'], row['voltage'],
                'N/A' if row['mean_mA'] is None else f"{row['mean_mA']:.4f}",
                'N/A (n<2)' if row['sd_mA'] is None else f"{row['sd_mA']:.4f}",
                'N/A' if row['energy_J'] is None else f"{row['energy_J']:.6f}"))
        self.order_table()
        preview = self.result['preview']
        if not keep_time:
            self.begin.set(str(preview['analysis_range'][0]))
            self.end.set(str(preview['analysis_range'][1] or preview['common_end']))
        self.status.set('Statistics: full repeats' if preview['analysis_range'][1] is None
                        else f"Statistics: [{self.begin.get()}, {self.end.get()}) s")

    def sort_table(self, column):
        previous, descending = self.table_sort
        self.table_sort = (column, not descending if previous == column else False)
        self.order_table()

    def order_table(self):
        column, descending = self.table_sort
        if column is None: return
        field = dict(session='display_name', n='repeats', duration='seconds', voltage='voltage',
                     mean='mean_mA', sd='sd_mA', energy='energy_J')[column]
        rows = self.selected_result['rows']
        available = [row for row in rows if row[field] is not None]
        available.sort(key=lambda row: row[field].casefold() if column == 'session' else row[field], reverse=descending)
        # Undefined statistics stay at the bottom in either sort direction.
        ordered = available + [row for row in rows if row[field] is None]
        for index, row in enumerate(ordered): self.table.move(row['id'], '', index)
        for key, heading in self.table_headings.items():
            self.table.heading(key, text=heading + (' ▼' if descending else ' ▲') if key == column else heading)

    def rename(self, session):
        if self.busy: return
        original = next(row['name'] for row in self.result['rows'] if row['id'] == session)
        self.display_names[session] = self.name_vars[session].get().strip() or original
        self.render(keep_time=True, keep_limits=True)

    def reset_name(self, session):
        if self.busy: return
        self.display_names.pop(session, None)
        self.render(keep_time=True, keep_limits=True)

    def toggle(self, session):
        if self.busy: return
        if session in self.hidden: self.hidden.remove(session)
        else: self.hidden.add(session)
        self.render(keep_time=True)

    def toggle_repeat(self, session, repeat):
        if self.busy: return
        key = (session, repeat)
        if key in self.excluded_repeats: self.excluded_repeats.remove(key)
        else: self.excluded_repeats.add(key)
        self.render(keep_time=True)

    def set_all_repeats(self, session, checked):
        if self.busy: return
        row = next(row for row in self.result['rows'] if row['id'] == session)
        keys = {(session, repeat) for repeat in row['repeat_names']}
        if checked: self.excluded_repeats.difference_update(keys)
        else: self.excluded_repeats.update(keys)
        self.render(keep_time=True)

    def dismiss_point(self, event=None):
        if event is not None:
            if event.name == 'key_press_event' and event.key != 'escape': return
            if event.name == 'button_press_event':
                if event.button == 1:
                    if self.toolbar.mode: return
                    if self.cursor and any(selection.annotation.contains(event)[0] for selection in self.cursor.selections): return
                    if any(line.axes is event.inaxes and line.contains(event)[0] for line, _, _ in self.plot.targets): return
                elif event.button != 3: return
        if self.cursor:
            for selection in self.cursor.selections:
                self.cursor.remove_selection(selection)

    def scroll(self, event):
        if self.busy or event.inaxes not in self.plot.axes or event.xdata is None: return
        self.toolbar.push_current()
        factor = 1 / 1.4 if event.button == 'up' else 1.4
        ax = event.inaxes
        for limits, anchor, setter in [(ax.get_xlim(), event.xdata, ax.set_xlim), (ax.get_ylim(), event.ydata, ax.set_ylim)]:
            setter(*[anchor+(value-anchor)*factor for value in limits])
        self.toolbar.push_current(); self.canvas.draw_idle()

    def use_view(self):
        low, high = self.plot.axes[0].get_xlim()
        self.begin.set(f'{max(0, low):.6f}')
        self.end.set(f"{min(high, self.result['preview']['common_end']):.6f}")

    def task(self, label, action, finished):
        self.busy = True; self.status.set(label); self.progress.pack(fill='x', padx=12); self.progress.start()
        for widget in [*self.buttons, *self.entries, *self.sessions.winfo_children()]: widget.configure(state='disabled')
        def work():
            try: self.queue.put((finished, action(), None))
            except Exception as error: self.queue.put((finished, None, error))
        Thread(target=work, daemon=True).start()

    def poll(self):
        if (self.directory / 'close.request').exists(): self.closing = True
        try:
            callback, result, error = self.queue.get_nowait()
            self.busy = False; self.progress.stop(); self.progress.pack_forget()
            for widget in [*self.buttons, *self.entries, *self.sessions.winfo_children()]: widget.configure(state='normal')
            if not self.closing:
                if error: self.status.set(f'Failed: {error}')
                else: callback(result)
        except Empty: pass
        if self.closing and not self.busy:
            self.data._close(); self.root.destroy(); return
        self.root.after(100, self.poll)

    def apply(self, full=False):
        try: begin, end = (0, None) if full else (float(self.begin.get()), float(self.end.get()))
        except ValueError: self.status.set('From and To must be numbers.'); return
        def finished(result): self.result = result; self.render()
        self.task('Recalculating from original samples…', lambda: self.data.apply_range(begin, end), finished)

    def save(self):
        from tkinter import filedialog
        if not any(row['id'] not in self.hidden and row['repeats'] for row in self.selected_result['rows']): return
        folder = filedialog.askdirectory(parent=self.root)
        if not folder: return
        # Snapshot prevents toolbar changes from affecting an export in progress.
        plot = ComparisonFigure(Figure(figsize=(14, 6), layout='constrained'), self.selected_result, self.hidden)
        plot.draw([(ax.get_xlim(), ax.get_ylim()) for ax in self.plot.axes])
        self.task('Saving figures…', lambda: plot.save(folder), lambda path: self.status.set(f'Saved to {path}'))

    def export(self):
        from tkinter import filedialog
        try: begin, end = float(self.begin.get()), float(self.end.get())
        except ValueError: self.status.set('From and To must be numbers.'); return
        folder = filedialog.askdirectory(parent=self.root)
        excluded = tuple(self.excluded_repeats)
        if folder: self.task('Exporting original samples…', lambda: self.data.export_selected_samples(folder, begin, end, excluded),
                            lambda path: self.status.set(f'Saved to {path}'))

    def close(self):
        self.closing = True
        if self.busy: self.status.set('Finishing current operation before closing…')


def create_root():
    # Windows Python 3.13 virtual environments can miss the base installation's Tcl path.
    libraries = Path(sys.base_prefix) / 'tcl'
    if sys.platform == 'win32' and libraries.is_dir():
        for variable, pattern in [('TCL_LIBRARY', 'tcl*/init.tcl'), ('TK_LIBRARY', 'tk*/tk.tcl')]:
            script = next(libraries.glob(pattern), None)
            if script: os.environ.setdefault(variable, str(script.parent))
    import tkinter as tk
    return tk.Tk()


def main():
    root = create_root()
    ComparisonWindow(root, sys.argv[1])
    root.update_idletasks()
    (Path(sys.argv[1]) / 'ready').touch()
    root.mainloop()


if __name__ == '__main__':
    main()
