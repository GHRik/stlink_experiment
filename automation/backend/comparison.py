"""Compare saved sessions without modifying their data or existing reports."""
import argparse
import base64
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap
from tempfile import TemporaryDirectory


def generate_comparison(root, names, output):
    import numpy as np
    from src.results import load_run, aggregate, envelope, plt, save_report_plot, Line2D

    root, output = Path(root).resolve(), Path(output)
    names = list(dict.fromkeys(names))
    if len(names) < 2:
        raise ValueError('Select at least two measurement sessions')
    output.mkdir(parents=True, exist_ok=True)
    traces, ax = plt.subplots(figsize=(10, 5))
    summary = []
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
                current = data['current_uA'] / 1000
                row = dict(configuration=name, voltage_V=meta['voltage_V'], sampling_Hz=hz,
                    begin_s=0, end_s=meta['requested_duration_s'],
                    conditions=json.dumps({'notes': meta.get('board_notes', ''), 'identity': meta.get('identity', {})}, sort_keys=True),
                    mean_current_mA=float(np.mean(current)),
                    energy_estimate_J=float(np.sum(current) / 1000 * meta['voltage_V'] / hz))
                envelope(ax, data['time_s'], current, label=f'S{index + 1}' if not rows else None, color=color)
                ax.lines[-1].set_alpha(.5)
                rows.append(row)
            if not rows:
                raise ValueError(f'No valid repeats in {name}')
            groups = aggregate(rows)
            if len(groups) != 1:
                raise ValueError(f'{name}: repeats have different voltage, sampling, duration or conditions; select a single consistent session')
            group = groups[0]
            summary.append(dict(id=f'S{index + 1}', name=name, repeats=len(rows), excluded=excluded,
                seconds=group['end_s'], voltage=group['voltage_V'],
                mean_mA=group['mean_current_mA_mean'], sd_mA=group['mean_current_mA_between_run_sd'],
                energy_J=group['energy_estimate_J_mean'], values=[row['mean_current_mA'] for row in rows],
                color=list(color)))
        ax.set(xlabel='Time from acquisition start [s]', ylabel='Current [mA]', title='Selected sessions — all valid repeats')
        ax.grid(alpha=.25)
        handles = [Line2D([], [], color=row['color'], label=f"{row['id']} · {textwrap.fill(row['name'], 60)}") for row in summary]
        save_report_plot(traces, output / 'comparison_traces',
            'One color per session. Bin mean lines and min–max envelopes; full data used for statistics.', handles)
        statistics, ax = plt.subplots(figsize=(7, 5))
        try:
            for index, row in enumerate(summary):
                offsets = np.linspace(-.15, .15, row['repeats']) if row['repeats'] > 1 else [0]
                ax.scatter(index + np.asarray(offsets), row['values'], color=row['color'], alpha=.8, s=26)
                ax.errorbar(index, row['mean_mA'], yerr=row['sd_mA'],
                            fmt='o', color=row['color'], markeredgecolor='black', capsize=6, linewidth=2, markersize=8)
            ax.set_xticks(range(len(summary)), [row['id'] for row in summary])
            ax.set(ylabel='Mean current [mA]', title='Mean ± sample SD between repeats')
            ax.grid(axis='y', alpha=.25)
            numbers = '\n'.join(f"{row['id']}: n={row['repeats']}; mean {row['mean_mA']:.4f} mA; "
                + (f"SD {row['sd_mA']:.4f} mA" if row['sd_mA'] is not None else 'SD n/a (n=1)') for row in summary)
            sd_note = 'SD requires at least two valid repeats.\n' if any(row['sd_mA'] is None for row in summary) else ''
            save_report_plot(statistics, output / 'comparison_statistics',
                'Small dots: repeat means. Large dot: session mean. Bars: ±1 SD (not min–max).\n'
                + sd_note + numbers, handles)
        finally:
            plt.close(statistics)
        (output / 'summary.json').write_text(json.dumps(summary, allow_nan=False), encoding='utf-8')
        return summary
    finally:
        plt.close(traces)


class ComparisonView:
    def __init__(self, webview, directory):
        self._webview, self._directory = webview, directory
        self._window = None

    def get_comparison(self):
        root = Path(self._directory.name)
        images = {key: 'data:image/png;base64,' + base64.b64encode((root / f'{key}.png').read_bytes()).decode('ascii')
                  for key in ('comparison_traces', 'comparison_statistics')}
        return dict(images=images, rows=json.loads((root / 'summary.json').read_text(encoding='utf-8')))

    def save_figures(self):
        selected = self._window.create_file_dialog(self._webview.FileDialog.FOLDER, allow_multiple=False)
        if not selected:
            return None
        folder = Path(selected[0]) / ('comparison_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        folder.mkdir()
        for base in ('comparison_traces', 'comparison_statistics'):
            for extension in ('png', 'svg'):
                shutil.copy2(Path(self._directory.name) / f'{base}.{extension}', folder)
        shutil.copy2(Path(self._directory.name) / 'summary.json', folder)
        return str(folder)

    def _close(self):
        self._directory.cleanup()


class ComparisonService:
    def __init__(self, webview, root):
        self._webview, self._root = webview, Path(root)

    def open(self, sessions):
        directory = TemporaryDirectory(prefix='stlink_comparison_')
        try:
            result = subprocess.run([sys.executable, '-m', 'automation.backend.comparison',
                '--root', str(self._root), '--out', directory.name, '--', *sessions],
                cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, encoding='utf-8', errors='replace',
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or result.stdout.strip())
            view = ComparisonView(self._webview, directory)
            view._window = self._webview.create_window('Measurement comparison',
                str(Path(__file__).resolve().parents[1] / 'frontend/comparison.html'), js_api=view,
                width=1400, height=900, min_size=(850, 600), text_select=True)
            view._window.events.closed += view._close
        except BaseException:
            directory.cleanup()
            raise
        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('sessions', nargs='+')
    args = parser.parse_args()
    generate_comparison(args.root, args.sessions, args.out)
