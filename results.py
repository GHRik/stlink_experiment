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
        for base in ("comparison", "statistics", "comparison_pl", "comparison_eng",
                     "statistics_pl", "statistics_eng"):
            for ext in ("png", "svg"):
                (root / f"{base}.{ext}").unlink(missing_ok=True)
        print("Zapisano CSV. Pominieto wspolne wykresy: rozne napiecia, Hz lub przedzialy czasu. "
              "Analizuj osobny katalog albo wybierz wspolny zakres --from-s/--to-s.")
        return
    for language in ("pl", "eng"):
        plot_report(root, rows, traces, stats, language)
    # Remove obsolete plots so they cannot be confused with the current reports.
    for base in ("comparison", "statistics"):
        for ext in ("png", "svg"):
            (root / f"{base}.{ext}").unlink(missing_ok=True)
    print(f"Analiza: {len(rows)} poprawnych pomiarow; wykluczono {len(errors)}.")


def plot_report(root, rows, traces, stats, language):
    labels = {
        "eng": ("Time from acquisition start [s]", "Current [mA]", "Repeat",
                "All repeats (individual traces)", "Mean current [mA]",
                "Estimated energy [J]", "Individual repeat", "Mean ± 1 SD (vertical bars)",
                "Summary across independent repeats"),
        "pl": ("Czas od rozpoczęcia pomiaru [s]", "Prąd [mA]", "Powtórzenie",
               "Wszystkie powtórzenia (osobne przebiegi)", "Średni prąd [mA]",
               "Szacowana energia [J]", "Pojedyncze powtórzenie", "Średnia ± 1 SD (pionowe kreski)",
               "Podsumowanie niezależnych powtórzeń"),
    }[language]
    time_label, current_label, repeat_label, comparison_title, mean_label, energy_label, point_label, sd_label, stats_title = labels
    summary_lines = []
    for k, runs in enumerate(traces.values(), 1):
        currents = [data["current_uA"] / 1000 for _, data in runs]
        average = sum(float(np.sum(values)) for values in currents) / sum(len(values) for values in currents)
        minimum = min(float(np.min(values)) for values in currents)
        maximum = max(float(np.max(values)) for values in currents)
        if language == "pl":
            values_text = f"Średni pobór: {average:.3f} mA | Maksymalny: {maximum:.3f} mA | Minimalny: {minimum:.3f} mA"
            values_text = values_text.replace(".", ",")
        else:
            values_text = f"Mean current: {average:.3f} mA | Maximum: {maximum:.3f} mA | Minimum: {minimum:.3f} mA"
        summary_lines.append(f'{runs[0][0]["configuration"]}: {values_text}')
        # Match the sample SD used by the statistics error bars, not within-trace fluctuations.
        current_sd = float(np.std([row["mean_current_mA"] for row, _ in runs], ddof=1)) if len(runs) > 1 else None
        energy_sd = float(np.std([row["energy_estimate_J"] for row, _ in runs], ddof=1)) if len(runs) > 1 else None
        if current_sd is None:
            sd_text = ("SD: nieokreślone (potrzeba co najmniej 2 powtórzeń)" if language == "pl"
                       else "SD: undefined (at least 2 repeats required)")
        elif language == "pl":
            sd_text = (f"Odchylenie standardowe między powtórzeniami (SD): "
                       f"średni prąd {current_sd:.3f} mA | energia {energy_sd:.6f} J").replace(".", ",")
        else:
            sd_text = (f"Standard deviation across repeats (SD): "
                       f"mean current {current_sd:.3f} mA | energy {energy_sd:.6f} J")
        summary_lines.append(sd_text)
    scope = ("Prąd ze wszystkich próbek w analizowanym przedziale, ze wszystkich powtórzeń."
             if language == "pl" else "Current across all samples in the analysis window, across all repeats.")
    footer = "\n".join(summary_lines + [scope])
    extra_height = 0.3 * len(summary_lines) + 0.5
    comparison_height = 5 + extra_height
    fig, axes = plt.subplots(1, len(traces), figsize=(max(10, 5 * len(traces)), comparison_height),
                             squeeze=False, sharex=True, sharey=True)
    for k, (ax, runs) in enumerate(zip(axes[0], traces.values()), 1):
        colors = plt.get_cmap("tab20", max(20, len(runs)))
        for number, (row, data) in enumerate(runs):
            envelope(ax, data["time_s"], data["current_uA"] / 1000,
                     label=f'{repeat_label} {number + 1}', color=colors(number))
        ax.set(xlabel=time_label,
               title=f'{row["configuration"]} | {row["voltage_V"]} V | n={len(runs)}')
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(alpha=0.25)
    axes[0, 0].set_ylabel(current_label)
    fig.suptitle(f"{root.name}\n{comparison_title}")
    fig.text(0.5, 0.02, footer, ha="center", va="bottom", fontsize=9, linespacing=1.6)
    plot_save(fig, root / f"comparison_{language}", bottom=extra_height / comparison_height)
    statistics_height = 5.5 + extra_height
    fig, axes = plt.subplots(1, 2, figsize=(12, statistics_height))
    repeat_handles = {}
    for ax, field, ylabel in zip(axes, ("mean_current_mA", "energy_estimate_J"),
                                 (mean_label, energy_label)):
        for i, group in enumerate(stats):
            matches = [r for r in rows if all(r[k] == group[k] for k in
                       ("configuration", "voltage_V", "sampling_Hz", "begin_s", "end_s", "conditions"))]
            values = [r[field] for r in matches]
            colors = plt.get_cmap("tab20", max(20, len(matches)))
            # Spread repeats horizontally so near-identical results remain visible.
            offsets = np.linspace(-0.15, 0.15, len(matches)) if len(matches) > 1 else [0]
            for number, (value, offset) in enumerate(zip(values, offsets)):
                point = ax.scatter(i + offset, value, color=colors(number), s=28,
                                   alpha=0.85, label=f"{repeat_label} {number + 1}")
                repeat_handles.setdefault(number, point)
            sd = group[field + "_between_run_sd"]
            mean = ax.errorbar(i, group[field + "_mean"], yerr=sd if sd is not None else 0,
                               fmt="o", color="black", capsize=5,
                               label=sd_label)
        ax.set_xticks(range(len(stats)), [f'{s["configuration"]}\n(n={s["n_runs"]})'
                                         for i, s in enumerate(stats)])
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle(f"{root.name}\n{stats_title}")
    fig.legend(handles=[*repeat_handles.values(), mean], loc="lower center", ncol=6,
               bbox_to_anchor=(0.5, (extra_height + 0.1) / statistics_height), frameon=False)
    fig.text(0.5, 0.02, footer, ha="center", va="bottom", fontsize=9, linespacing=1.6)
    plot_save(fig, root / f"statistics_{language}", bottom=(extra_height + 0.65) / statistics_height)

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

