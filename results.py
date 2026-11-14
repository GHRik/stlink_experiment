"""Obliczenia i wykresy. Dane wejsciowe pozostaja niezmienione."""
from pathlib import Path
import json
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import t as student_t
from storage import save_json, write_csv

def envelope(ax, x, y, label=None, color=None):
    # Only plots are reduced: keep per-bin MIN/MAX, so narrow peaks remain visible.
    bins = min(2500, len(x))
    if bins == 0:
        return
    edges = np.linspace(0, len(x), bins + 1, dtype=int)
    centers, mins, maxs, means = [], [], [], []
    for a, b in zip(edges[:-1], edges[1:]):
        centers.append((x[a] + x[b - 1]) / 2)
        mins.append(float(np.min(y[a:b])))
        maxs.append(float(np.max(y[a:b])))
        means.append(float(np.mean(y[a:b])))
    line, = ax.plot(centers, means, label=label, color=color, linewidth=0.8)
    ax.fill_between(centers, mins, maxs, color=line.get_color(), alpha=0.25, linewidth=0)

def plot_save(fig, base, bottom=0):
    fig.tight_layout(rect=(0, bottom, 1, 1))
    for ext in ("png", "svg"):
        fig.savefig(base.with_suffix("." + ext), dpi=160)
    plt.close(fig)

def load_run(directory):
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    if meta["status"] != "valid":
        raise ValueError(f"Nieprawidlowy pomiar: {directory}")
    data = np.genfromtxt(directory / "samples.csv", delimiter=";", names=True, encoding="utf-8-sig")
    data = np.atleast_1d(data)
    hz = meta["sampling_Hz"]
    if len(data) != meta["samples"] or not np.array_equal(data["sample_index"], np.arange(len(data))):
        raise ValueError(f"Brakujace/powtorzone rekordy CSV: {directory}")
    return meta, data, hz

def analyze_run(directory, begin, end):
    meta, data, hz = load_run(directory)
    end = meta["requested_duration_s"] if end is None else end
    if begin < 0 or end <= begin or end > meta["requested_duration_s"] + 1e-8:
        raise ValueError(f"Zakres {begin}..{end} poza pomiarem: {directory}")
    a, b = round(begin * hz), round(end * hz)
    if not math.isclose(begin * hz, a) or not math.isclose(end * hz, b):
        raise ValueError("Granice analizy musza trafiac w siatke probek.")
    current = data["current_uA"][a:b] / 1000
    duration = len(current) / hz
    row = {
        "configuration": meta["configuration"], "run": directory.name,
        "directory": str(directory.resolve()), "voltage_V": meta["voltage_V"],
        "sampling_Hz": hz, "begin_s": begin, "end_s": end,
        "duration_s": duration, "samples": len(current),
        "mean_current_mA": float(np.mean(current)),
        "min_current_mA": float(np.min(current)),
        "max_current_mA": float(np.max(current)),
        "within_run_sd_mA": float(np.std(current, ddof=1)) if len(current) > 1 else None,
        "mean_power_mW": float(np.mean(current) * meta["voltage_V"]),
        "energy_estimate_J": float(np.sum(current) / 1000 * meta["voltage_V"] / hz),
    }
    save_json(directory / "analysis.json", row)
    fig, ax = plt.subplots(figsize=(11, 4))
    envelope(ax, data["time_s"][a:b], current)
    ax.set(xlabel="Time from acquisition start [s]", ylabel="Current [mA]",
           title=f'{meta["configuration"]} | {directory.name}')
    ax.grid(alpha=0.25)
    plot_save(fig, directory / "current")
    return row, data[a:b]

def aggregate(rows):
    # Never pool different voltage, sampling, notes, firmware or windows.
    groups = {}
    for row in rows:
        key = tuple(row[k] for k in ("configuration", "voltage_V", "sampling_Hz", "begin_s", "end_s", "conditions"))
        groups.setdefault(key, []).append(row)
    result = []
    for key, runs in groups.items():
        out = dict(zip(("configuration", "voltage_V", "sampling_Hz", "begin_s", "end_s", "conditions"), key))
        out["n_runs"] = len(runs)
        for field in ("mean_current_mA", "energy_estimate_J"):
            values = np.array([r[field] for r in runs])
            mean = float(np.mean(values))
            sd = float(np.std(values, ddof=1)) if len(values) > 1 else None
            half = float(student_t.ppf(0.975, len(values) - 1) * sd / np.sqrt(len(values))) if sd is not None else None
            out[field + "_mean"] = mean
            out[field + "_between_run_sd"] = sd
            out[field + "_ci95_low"] = mean - half if half is not None else None
            out[field + "_ci95_high"] = mean + half if half is not None else None
        result.append(out)
    return result

def report(root, begin, end):
    rows, traces = [], {}
    errors = []
    for file in sorted(root.rglob("metadata.json")):
        meta = json.loads(file.read_text(encoding="utf-8"))
        if meta.get("status") != "valid":
            errors.append({"directory": str(file.parent), "issues": meta.get("issues", [])})
            continue
        row, data = analyze_run(file.parent, begin, end)
        row["conditions"] = json.dumps({"board_notes": meta.get("board_notes", ""),
                                       "identity": meta.get("identity", {})}, sort_keys=True)
        rows.append(row)
        key = (row["configuration"], row["voltage_V"], row["sampling_Hz"],
               row["begin_s"], row["end_s"], row["conditions"])
        traces.setdefault(key, []).append((row, data))
    if not rows:
        raise ValueError("Brak poprawnych pomiarow do analizy.")
    # Prevent confusing comparisons across different time windows or voltage.
    write_csv(root / "runs_summary.csv", rows)
    stats = aggregate(rows)
    write_csv(root / "statistics.csv", stats)
    save_json(root / "excluded_runs.json", errors)
    settings = {tuple(r[k] for k in ("voltage_V", "sampling_Hz", "begin_s", "end_s")) for r in rows}
    if len(settings) > 1:
        for filename in ("comparison.png", "comparison.svg", "statistics.png", "statistics.svg"):
            (root / filename).unlink(missing_ok=True)
        print("Zapisano CSV. Pominieto wspolne wykresy: rozne napiecia, Hz lub przedzialy czasu. "
              "Analizuj osobny katalog albo wybierz wspolny zakres --from-s/--to-s.")
        return
    fig, axes = plt.subplots(1, len(traces), figsize=(max(8, 5 * len(traces)), 5),
                             squeeze=False, sharex=True, sharey=True)
    for k, (ax, runs) in enumerate(zip(axes[0], traces.values()), 1):
        colors = plt.get_cmap("tab20", max(20, len(runs)))
        for number, (row, data) in enumerate(runs):
            envelope(ax, data["time_s"], data["current_uA"] / 1000,
                     label=f'Run {number + 1}', color=colors(number))
        ax.set(xlabel="Time from acquisition start [s]",
               title=f'{row["configuration"]} | group {k} | {row["voltage_V"]} V')
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(alpha=0.25)
    axes[0, 0].set_ylabel("Current [mA]")
    fig.suptitle("All repeats (individual traces)")
    plot_save(fig, root / "comparison")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, field, ylabel in zip(axes, ("mean_current_mA", "energy_estimate_J"),
                                 ("Mean current [mA]", "Estimated energy [J]")):
        for i, group in enumerate(stats):
            matches = [r for r in rows if all(r[k] == group[k] for k in
                       ("configuration", "voltage_V", "sampling_Hz", "begin_s", "end_s", "conditions"))]
            values = [r[field] for r in matches]
            points = ax.scatter(np.full(len(values), i), values, color="tab:blue", s=20,
                                alpha=0.6, label="Individual run")
            sd = group[field + "_between_run_sd"]
            mean = ax.errorbar(i, group[field + "_mean"], yerr=sd if sd is not None else 0,
                               fmt="o", color="black", capsize=5,
                               label="Mean ± SD across runs")
        ax.set_xticks(range(len(stats)), [f'{s["configuration"]}\ngroup {i+1} (n={s["n_runs"]})'
                                         for i, s in enumerate(stats)])
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("Summary across independent runs")
    fig.legend(handles=[points, mean], loc="lower center", ncol=2,
               bbox_to_anchor=(0.5, 0.01), frameon=False)
    plot_save(fig, root / "statistics", bottom=0.1)
    print(f"Analiza: {len(rows)} poprawnych pomiarow; wykluczono {len(errors)}.")

def demo(out):
    """Synthetic inputs only; exercise reports without hardware."""
    root = Path(out)
    root.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    hz, seconds = 100, 30
    for label, idle in (("DEMO_modem", 20.8), ("DEMO_light", 1.0), ("DEMO_deep", 0.3)):
        for repeat in range(1, 4):
            directory = root / label / f"run_{repeat:03d}"
            directory.mkdir(parents=True, exist_ok=True)
            x = np.arange(hz * seconds) / hz
            current_mA = np.where(x % 10 < 2, 22.0, idle) + rng.normal(0, 0.005, len(x))
            current_mA += (repeat - 2) * 0.01
            data = ({"sample_index": i, "time_s": x[i], "current_uA": current_mA[i] * 1000,
                     "voltage_V": 3.3, "power_mW": current_mA[i] * 3.3,
                     "energy_estimate_J": energy} for i, energy in
                    enumerate(np.cumsum(current_mA / 1000 * 3.3 / hz)))
            write_csv(directory / "samples.csv", data)
            save_json(directory / "metadata.json", {
                "configuration": label, "repeat": repeat, "voltage_V": 3.3, "sampling_Hz": hz,
                "requested_duration_s": seconds, "samples": hz * seconds,
                "status": "valid", "issues": [], "board_notes": "SYNTHETIC DATA, NOT A MEASUREMENT",
                "identity": {"whoami": "SIMULATED"}})
    report(root, 0, None)

