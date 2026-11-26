"""Compare saved sessions without modifying their data or existing reports."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap
import math
from threading import RLock, Thread
import time
from tempfile import TemporaryDirectory


def select_samples(meta, data, begin=0, end=None):
    end = meta['requested_duration_s'] if end is None else end
    if not math.isfinite(begin) or not math.isfinite(end) or begin < 0 or end <= begin or end > meta['requested_duration_s'] + 1e-8:
        raise ValueError(f'Range must fit every repeat: 0 <= From < To <= {meta["requested_duration_s"]:g} s')
    selected = data[(data['time_s'] >= begin) & (data['time_s'] < end)]
    if not len(selected):
        raise ValueError('The selected interval contains no samples')
    return selected, end


def generate_comparison(root, names, output, begin=0, end=None, view=None, render=False, hidden=()):
    import numpy as np
    from src.results import load_run, aggregate, envelope, plt, save_report_plot, Line2D

    root, output = Path(root).resolve(), Path(output)
    names = list(dict.fromkeys(names))
    if len(names) < 2:
        raise ValueError('Select at least two measurement sessions')
    output.mkdir(parents=True, exist_ok=True)
    traces, ax = plt.subplots(figsize=(10, 5)) if render else (None, None)
    summary, series, durations = [], [], []
    palette = plt.get_cmap('tab20')
    try:
        for index, name in enumerate(names):
            folder = (root / name).resolve()
            if not folder.is_relative_to(root) or not folder.is_dir():
                raise ValueError(f'Session is not inside results: {name}')
            rows, excluded = [], 0
            # Use saturated colors first, followed by their lighter variants.
            color = palette((index % 10) * 2 + (index // 10) % 2)
            for file in sorted(folder.rglob('metadata.json')):
                if json.loads(file.read_text(encoding='utf-8-sig')).get('status') != 'valid':
                    excluded += 1
                    continue
                meta, data, hz = load_run(file.parent)
                durations.append(meta['requested_duration_s'])
                data, stop = select_samples(meta, data, begin, end)
                current = data['current_uA'] / 1000
                row = dict(configuration=name, voltage_V=meta['voltage_V'], sampling_Hz=hz,
                    repeat=file.parent.name,
                    begin_s=begin, end_s=stop, duration_s=len(data) / hz,
                    conditions=json.dumps({'notes': meta.get('board_notes', ''), 'identity': meta.get('identity', {}),
                                           'source_duration_s': meta['requested_duration_s']}, sort_keys=True),
                    mean_current_mA=float(np.mean(current)),
                    energy_estimate_J=float(np.sum(current) / 1000 * meta['voltage_V'] / hz))
                display = (data['time_s'] >= view[0]) & (data['time_s'] <= view[1]) if view else np.ones(len(data), dtype=bool)
                if render and f'S{index+1}' not in hidden:
                    envelope(ax, data['time_s'][display], current[display], label=f'S{index + 1}' if not rows else None, color=color)
                edges = np.linspace(0, len(data), min(1200, len(data)) + 1, dtype=int)
                points = [[float((data['time_s'][a] + data['time_s'][b-1]) / 2),
                           float(np.mean(current[a:b])), float(np.min(current[a:b])), float(np.max(current[a:b]))]
                          for a, b in zip(edges[:-1], edges[1:])]
                series.append(dict(id=f'S{index+1}', name=name, repeat=file.parent.name, color=list(color), points=points))
                if render and f'S{index+1}' not in hidden and np.any(display): ax.lines[-1].set_alpha(.5)
                rows.append(row)
            if not rows:
                raise ValueError(f'No valid repeats in {name}')
            groups = aggregate(rows)
            if len(groups) != 1:
                raise ValueError(f'{name}: repeats have different voltage, sampling, duration or conditions; select a single consistent session')
            group = groups[0]
            summary.append(dict(id=f'S{index + 1}', name=name, repeats=len(rows), excluded=excluded,
                seconds=rows[0]['duration_s'], begin_s=begin, end_s=group['end_s'], voltage=group['voltage_V'],
                mean_mA=group['mean_current_mA_mean'], sd_mA=group['mean_current_mA_between_run_sd'],
                energy_J=group['energy_estimate_J_mean'], values=[row['mean_current_mA'] for row in rows],
                repeat_energies_J=[row['energy_estimate_J'] for row in rows],
                repeat_names=[row['repeat'] for row in rows],
                color=list(color), visible=f'S{index+1}' not in hidden))
        (output / 'summary.json').write_text(json.dumps(summary, allow_nan=False), encoding='utf-8')
        (output / 'preview.json').write_text(json.dumps(dict(series=series, bounds=[begin, end if end is not None else max(durations)],
            common_end=min(durations), analysis_range=[begin, end]), allow_nan=False), encoding='utf-8')
        (output / 'context.json').write_text(json.dumps(dict(root=str(root), names=names, begin=begin, end=end)), encoding='utf-8')
        if not render:
            return summary
        visible = [row for row in summary if row['visible']]
        if not visible:
            raise ValueError('Show at least one session before saving figures')
        ax.set(xlabel='Time from acquisition start [s]', ylabel='Current [mA]', title='Selected sessions — all valid repeats')
        if view:
            if not all(math.isfinite(value) for value in view) or not begin <= view[0] < view[1] <= (end if end is not None else max(durations)):
                raise ValueError('Zoom must lie inside the analysis window')
            ax.set_xlim(*view)
        ax.grid(alpha=.25)
        handles = [Line2D([], [], color=row['color'], label=f"{row['id']} · {textwrap.fill(row['name'], 60)}") for row in visible]
        range_note = f'Analysis range: [{begin:g}, {end:g}) s.' if end is not None else 'Analysis range: full repeats.'
        view_note = f' View: {view[0]:g}–{view[1]:g} s; statistics are unchanged by zoom.' if view else ''
        save_report_plot(traces, output / 'comparison_traces',
            'One color per session. Bin mean lines and min–max envelopes.\n' + range_note + view_note, handles)
        statistics, ax = plt.subplots(figsize=(7, 5))
        try:
            for index, row in enumerate(summary):
                if not row['visible']: continue
                offsets = np.linspace(-.15, .15, row['repeats']) if row['repeats'] > 1 else [0]
                ax.scatter(index + np.asarray(offsets), row['values'], color=row['color'], alpha=.8, s=26)
                ax.errorbar(index, row['mean_mA'], yerr=row['sd_mA'],
                            fmt='o', color=row['color'], markeredgecolor='black', capsize=6, linewidth=2, markersize=8)
            ax.set_xticks(range(len(summary)), [row['id'] for row in summary])
            ax.set(ylabel='Mean current [mA]', title='Mean ± sample SD between repeats')
            ax.grid(axis='y', alpha=.25)
            numbers = '\n'.join(f"{row['id']}: n={row['repeats']}; mean {row['mean_mA']:.4f} mA; "
                + (f"SD {row['sd_mA']:.4f} mA" if row['sd_mA'] is not None else 'SD n/a (n=1)') for row in visible)
            sd_note = 'SD requires at least two valid repeats.\n' if any(row['sd_mA'] is None for row in visible) else ''
            save_report_plot(statistics, output / 'comparison_statistics',
                'Small dots: repeat means. Large dot: session mean. Bars: ±1 SD (not min–max).\n'
                + range_note + '\n' + sd_note + numbers, handles)
        finally:
            plt.close(statistics)
        return summary
    finally:
        if traces is not None: plt.close(traces)


def export_samples(root, names, output, begin=0, end=None, excluded=()):
    import numpy as np
    from src.results import load_run
    from src.storage import write_csv
    root, output = Path(root).resolve(), Path(output)
    exported = []
    for index, name in enumerate(names, 1):
        source = (root / name).resolve()
        if not source.is_relative_to(root): raise ValueError('Session is not inside results')
        for file in sorted(source.rglob('metadata.json')):
            if (f'S{index}', file.parent.name) in excluded: continue
            if json.loads(file.read_text(encoding='utf-8-sig')).get('status') != 'valid': continue
            meta, data, hz = load_run(file.parent)
            data, stop = select_samples(meta, data, begin, end)
            data = data.copy()
            if 'energy_estimate_J' in data.dtype.names:
                data['energy_estimate_J'] = np.cumsum(data['current_uA']) / 1e6 * meta['voltage_V'] / hz
            target = output / f'S{index}' / file.parent.relative_to(source) / 'samples.csv'
            target.parent.mkdir(parents=True, exist_ok=True)
            write_csv(target, ({key: int(row[key]) if key == 'sample_index' else float(row[key]) for key in data.dtype.names} for row in data), fields=data.dtype.names)
            exported.append(dict(session=name, source=str(file.parent), file=target.relative_to(output).as_posix(),
                                 begin_s=begin, end_s=stop, samples=len(data), sampling_Hz=hz))
    (output / 'selection.json').write_text(json.dumps(dict(repeats=exported,
        note='Original timestamps and sample indices retained; cumulative energy starts at the selected interval.'), indent=2), encoding='utf-8')


def run_comparison(root, names, output, begin=0, end=None, view=None, samples=False, render=False, hidden=(), excluded=()):
    command = [sys.executable, '-m', 'automation.backend.comparison', '--root', str(root), '--out', str(output), '--from-s', str(begin)]
    if end is not None: command += ['--to-s', str(end)]
    if view: command += ['--view', *map(str, view)]
    if samples: command += ['--export-samples']
    if excluded: command += ['--excluded-repeats', json.dumps(sorted(excluded))]
    if render: command += ['--render']
    if hidden: command += ['--hidden', *hidden]
    result = subprocess.run([*command, '--', *names], cwd=Path(__file__).resolve().parents[2],
        capture_output=True, text=True, encoding='utf-8', errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode: raise RuntimeError(result.stderr.strip() or result.stdout.strip())


class ComparisonData:
    def __init__(self, directory):
        self._directory = directory
        self._lock = RLock()
        self._closed = False

    def get_comparison(self):
        with self._lock:
            if self._closed: raise RuntimeError('Comparison window is closed')
            root = Path(self._directory.name)
            return dict(rows=json.loads((root / 'summary.json').read_text(encoding='utf-8')),
                        preview=json.loads((root / 'preview.json').read_text(encoding='utf-8')))

    def _render(self, begin, end, view=None, render=False, hidden=()):
        if self._closed: raise RuntimeError('Comparison window is closed')
        root = Path(self._directory.name)
        context = json.loads((root / 'context.json').read_text(encoding='utf-8'))
        # Failed recalculation cannot replace the last successful comparison.
        with TemporaryDirectory(prefix='work_', dir=root) as stage:
            run_comparison(context['root'], context['names'], stage, begin, end, view, render=render, hidden=hidden)
            for file in Path(stage).iterdir(): shutil.copy2(file, root)

    def apply_range(self, begin=0, end=None):
        with self._lock:
            self._render(begin, end)
            return self.get_comparison()

    def export_selected_samples(self, destination, begin, end, excluded=()):
        with self._lock:
            if self._closed: raise RuntimeError('Comparison window is closed')
            root = Path(self._directory.name)
            context = json.loads((root / 'context.json').read_text(encoding='utf-8'))
            with TemporaryDirectory(prefix='csv_', dir=root) as stage:
                run_comparison(context['root'], context['names'], stage, begin, end, samples=True, excluded=excluded)
                folder = Path(destination) / ('selected_samples_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
                shutil.copytree(stage, folder)
            return str(folder)

    def _close(self):
        with self._lock:
            self._closed = True
            self._directory.cleanup()


class ComparisonService:
    def __init__(self, webview, root):
        self._webview, self._root = webview, Path(root)
        self._children = []
        self._lock = RLock()

    def close(self):
        with self._lock:
            children = list(self._children)
        for process, directory in children:
            if process.poll() is None:
                (Path(directory.name) / 'close.request').touch()
        for process, _ in children:
            process.wait()

    def open(self, sessions):
        directory = TemporaryDirectory(prefix='stlink_comparison_')
        try:
            run_comparison(self._root, sessions, directory.name)
            log = Path(directory.name) / 'window.log'
            with log.open('w', encoding='utf-8') as stream:
                process = subprocess.Popen([sys.executable, '-m', 'automation.backend.comparison_window', directory.name],
                    cwd=Path(__file__).resolve().parents[2], stdout=stream, stderr=stream,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            def cleanup():
                process.wait()
                directory.cleanup()
                with self._lock:
                    self._children.remove((process, directory))
            deadline = time.monotonic() + 30
            while not (Path(directory.name) / 'ready').exists():
                if process.poll() is not None:
                    raise RuntimeError(log.read_text(encoding='utf-8') or 'Comparison window could not start')
                if time.monotonic() > deadline:
                    process.terminate()
                    process.wait()
                    raise RuntimeError('Comparison window startup timed out')
                time.sleep(.05)
            with self._lock:
                self._children.append((process, directory))
            Thread(target=cleanup, daemon=True).start()
        except BaseException:
            directory.cleanup()
            raise
        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--from-s', type=float, default=0)
    parser.add_argument('--to-s', type=float)
    parser.add_argument('--view', type=float, nargs=2)
    parser.add_argument('--export-samples', action='store_true')
    parser.add_argument('--excluded-repeats', type=json.loads, default=[])
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--hidden', nargs='+', default=[])
    parser.add_argument('sessions', nargs='+')
    args = parser.parse_args()
    if args.export_samples:
        export_samples(args.root, args.sessions, args.out, args.from_s, args.to_s, {tuple(key) for key in args.excluded_repeats})
    else:
        generate_comparison(args.root, args.sessions, args.out, args.from_s, args.to_s, args.view, args.render, args.hidden)
