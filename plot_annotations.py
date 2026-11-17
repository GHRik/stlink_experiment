"""Consistent extrema markers and per-repeat captions for measurement plots."""
import textwrap
import numpy as np
from matplotlib.offsetbox import TextArea, HPacker, VPacker

MIN_COLOR = "#9ed5ff"
MAX_COLOR = "#ffc078"


def number(value, language="eng", precision=3):
    text = f"{value:.{precision}f}"
    return text.replace(".", ",") if language == "pl" else text


def extrema(x, y):
    if not len(y):
        return None
    low, high = int(np.argmin(y)), int(np.argmax(y))
    return ((float(x[low]), float(y[low])), (float(x[high]), float(y[high])))


def mark_extrema(ax, limits, language="eng", scope=""):
    """Annotate original sample extrema, even when the displayed line is averaged."""
    if limits is None:
        return
    for (time, value), name, color, height in (
            (limits[0], "Min", MIN_COLOR, 0.05),
            (limits[1], "Maks." if language == "pl" else "Max", MAX_COLOR, 0.95)):
        ax.scatter([time], [value], s=45, facecolor=color, edgecolor="black", linewidth=0.6, zorder=6)
        label = (f"{name}{' ' + scope if scope else ''}: {number(value, language)} mA\n"
                 f"t = {number(time, language)} s")
        left, right = ax.get_xlim()
        label_on_left = time > (left + right) / 2
        ax.annotate(label, xy=(time, value), xytext=(0.03 if label_on_left else 0.97, height),
                    textcoords="axes fraction", ha="left" if label_on_left else "right",
                    va="top" if height > 0.5 else "bottom", fontsize=9,
                    fontweight="bold", bbox=dict(facecolor=color, edgecolor="none", alpha=0.95, pad=4),
                    arrowprops=dict(arrowstyle="->", color="black"))
    ax.margins(y=0.30)


def text_box(text, color="black", kind=None, bold=False):
    props = dict(color=color, fontsize=9, fontweight="bold" if bold or kind else "normal")
    if kind:
        props["bbox"] = dict(facecolor=MIN_COLOR if kind == "min" else MAX_COLOR,
                             edgecolor="none", pad=2)
    return TextArea(text, textprops=props)


def hpack(items):
    return HPacker(children=items, align="baseline", pad=2, sep=7)


def column(title, blocks):
    return VPacker(children=[text_box(title, bold=True), *blocks], align="left", pad=4, sep=7)


def same(a, b):
    # Highlight every tied winner without hiding a real, small difference.
    return a == b


def range_row(label, limits, minimum, maximum, language="eng", color="black"):
    if limits is None:
        return hpack([text_box("●", color=color), text_box(label), text_box("—")])
    low, high = limits[0][1], limits[1][1]
    return hpack([text_box("●", color=color), text_box(label),
                  text_box(f"min {number(low, language)} mA", kind="min" if same(low, minimum) else None),
                  text_box(f"max {number(high, language)} mA", kind="max" if same(high, maximum) else None)])


def range_summary(minimum, maximum, unit, language="eng"):
    return hpack([text_box(f"Min: {number(minimum, language)} {unit}", kind="min"),
                  text_box(f"Max: {number(maximum, language)} {unit}", kind="max")])


def trace_captions(groups, split, language="eng"):
    """Two caption columns with raw per-repeat ranges, scoped to the plotted panels."""
    columns = []
    for startup in (False, True):
        blocks = []
        for configuration, runs in groups:
            records = []
            for label, color, x, y in runs:
                mask = (x < split) & (x >= 0) if startup else x >= split
                records.append((label, color, extrema(x[mask], y[mask])))
            present = [limits for _, _, limits in records if limits is not None]
            blocks.append(text_box(textwrap.fill(configuration, 52), bold=True))
            if not present:
                blocks.append(text_box("Brak próbek" if language == "pl" else "No samples"))
                continue
            minimum = min(limits[0][1] for limits in present)
            maximum = max(limits[1][1] for limits in present)
            blocks.extend(range_row(label, limits, minimum, maximum, language, color)
                          for label, color, limits in records)
            if len(records) > 1:
                blocks.append(range_summary(minimum, maximum, "mA", language))
        title = (("Prawy panel — rozruch" if startup else "Lewy panel — po rozruchu")
                 if language == "pl" else ("Right panel — startup" if startup else "Left panel — after startup"))
        columns.append(column(title, blocks))
    return columns


def statistics_captions(groups, language="eng"):
    columns = []
    for field, unit, title in (
            ("mean_current_mA", "mA", "Średni prąd" if language == "pl" else "Mean current"),
            ("energy_estimate_J", "J", "Energia pomiaru" if language == "pl" else "Energy per repeat")):
        blocks = []
        for configuration, runs in groups:
            values = [row[field] for _, _, row in runs]
            low, high = min(values), max(values)
            blocks.append(text_box(textwrap.fill(configuration, 52), bold=True))
            for label, color, row in runs:
                value = row[field]
                parts = [text_box("●", color=color), text_box(label)]
                if same(value, low):
                    parts.append(text_box(f"{number(value, language)} {unit} (min)", kind="min"))
                if same(value, high):
                    parts.append(text_box(f"{number(value, language)} {unit} (max)", kind="max"))
                if not same(value, low) and not same(value, high):
                    parts.append(text_box(f"{number(value, language)} {unit}"))
                blocks.append(hpack(parts))
            blocks.append(range_summary(low, high, unit, language))
        columns.append(column(title, blocks))
    return columns
