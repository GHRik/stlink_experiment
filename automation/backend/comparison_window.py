"""Native Matplotlib comparison window; launched separately from pywebview."""
from datetime import datetime
import json
import os
from pathlib import Path
from queue import Queue, Empty
import sys
import textwrap
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


class ComparisonFigure:
    """Matplotlib artists shared by the desktop view and explicit exports."""

    def __init__(self, figure, result, hidden=()):
        self.figure, self.result, self.hidden = figure, result, set(hidden)
        self.axes = figure.subplots(1, 2)
        self.targets = []
        self.draw()

    def draw(self, limits=None):
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
        handles = [Line2D([], [], color=row['color'], label=f"{row['id']} · {textwrap.fill(row.get('display_name', row['name']), 40)}\n"
                   + textwrap.fill('Repeats: ' + ', '.join(name.removeprefix('repeat_') for name in row['repeat_names']), 50))
                   for row in self.result['rows'] if row['id'] not in self.hidden and row['repeats']]
        if handles:
            for ax in self.axes:
                ax.legend(handles=handles, loc='upper center', bbox_to_anchor=(.5, -.18), fontsize=7)

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
        export = Figure(figsize=(14, 6), layout='constrained')
        plots = ComparisonFigure(export, self.result, self.hidden)
        plots.draw(limits)
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        FigureCanvasAgg(export).draw()
        for ax, base in zip(plots.axes, ('comparison_traces', 'comparison_statistics')):
            bbox = ax.get_tightbbox(export.canvas.get_renderer()).transformed(export.dpi_scale_trans.inverted()).expanded(1.03, 1.08)
            for extension in ('png', 'svg'):
                export.savefig(folder / f'{base}.{extension}', bbox_inches=bbox, dpi=180)
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
        self.display_names, self.name_vars = {}, {}
        self.cursor = None
        self.queue = Queue()
        root.title('Measurement comparison — Matplotlib Figure')
        root.geometry('1400x900'); root.minsize(900, 650)
        controls = ttk.Frame(root, padding=8); controls.pack(fill='x')
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
        self.status = tk.StringVar(value='')
        ttk.Label(root, textvariable=self.status, font=('Segoe UI', 12)).pack(fill='x', padx=12)
        self.progress = ttk.Progressbar(root, mode='indeterminate')
        self.sessions = ttk.Frame(root, padding=8); self.sessions.pack(fill='x')
        self.figure = Figure(figsize=(14, 5), layout='constrained')
        self.canvas = FigureCanvasTkAgg(self.figure, master=root)
        self.toolbar = NavigationToolbar2Tk(self.canvas, root, pack_toolbar=False)
        self.toolbar.pack(fill='x')
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        columns = ('session', 'n', 'duration', 'voltage', 'mean', 'sd', 'energy')
        self.table = ttk.Treeview(root, columns=columns, show='headings', height=4)
        for key, heading in zip(columns, ('Session', 'Repeats', 'Duration [s]', 'Voltage [V]', 'Mean [mA]', 'SD [mA]', 'Energy [J]')):
            self.table.heading(key, text=heading); self.table.column(key, width=110 if key != 'session' else 400)
        self.table.pack(fill='x', padx=8, pady=8)
        self.canvas.mpl_connect('scroll_event', self.scroll)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.render()
        root.after(100, self.poll)

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
        for child in self.sessions.winfo_children(): child.destroy()
        self.selection_vars.clear()
        self.name_vars.clear()
        for index, row in enumerate(self.result['rows']):
            sid = row['id']
            variable = self.selection_vars[(sid, None)] = tk.BooleanVar(value=sid not in self.hidden)
            color = '#%02x%02x%02x' % tuple(round(c*255) for c in row['color'][:3])
            button = tk.Checkbutton(self.sessions, text=f"{row['id']} · {row['name']}", variable=variable,
                foreground=color, anchor='w', command=lambda sid=row['id']: self.toggle(sid))
            button.grid(row=index, column=0, sticky='w', padx=5)
            count = sum((sid, name) not in self.excluded_repeats for name in row['repeat_names'])
            repeats = ttk.Menubutton(self.sessions, text=f'Repeats ({count}/{row["repeats"]})')
            menu = tk.Menu(repeats, tearoff=False)
            repeats.configure(menu=menu)
            repeats.grid(row=index, column=1, sticky='w')
            for name in row['repeat_names']:
                variable = self.selection_vars[(sid, name)] = tk.BooleanVar(value=(sid, name) not in self.excluded_repeats)
                menu.add_checkbutton(label=name, variable=variable,
                    command=lambda sid=sid, name=name: self.toggle_repeat(sid, name))
            ttk.Label(self.sessions, text='Legend name:').grid(row=index, column=2, padx=(12, 4))
            name_var = self.name_vars[sid] = tk.StringVar(value=self.display_names.get(sid, row['name']))
            entry = ttk.Entry(self.sessions, textvariable=name_var, width=32)
            entry.grid(row=index, column=3, sticky='ew')
            entry.bind('<Return>', lambda event, sid=sid: self.rename(sid))
            ttk.Button(self.sessions, text='Rename', command=lambda sid=sid: self.rename(sid)).grid(row=index, column=4, padx=4)
        self.table.delete(*self.table.get_children())
        for row in self.selected_result['rows']:
            self.table.insert('', 'end', values=(row['display_name'], row['repeats'], row['seconds'], row['voltage'],
                'N/A' if row['mean_mA'] is None else f"{row['mean_mA']:.4f}",
                'N/A (n<2)' if row['sd_mA'] is None else f"{row['sd_mA']:.4f}",
                'N/A' if row['energy_J'] is None else f"{row['energy_J']:.6f}"))
        preview = self.result['preview']
        if not keep_time:
            self.begin.set(str(preview['analysis_range'][0]))
            self.end.set(str(preview['analysis_range'][1] or preview['common_end']))
        self.status.set('Statistics: full repeats' if preview['analysis_range'][1] is None
                        else f"Statistics: [{self.begin.get()}, {self.end.get()}) s")

    def rename(self, session):
        if self.busy: return
        original = next(row['name'] for row in self.result['rows'] if row['id'] == session)
        self.display_names[session] = self.name_vars[session].get().strip() or original
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
