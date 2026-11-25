# Interpreting the plots

[Quick Start](../README.md#quick-start) · [Methodology](methodology.md) · [Output files](outputs.md)

- Measurements cover the **whole powered board**, not just the microcontroller.
- Energy is estimated from current samples and configured voltage; voltage is not separately sampled.
- ±SD describes variation **between repeat results**, not the minimum-to-maximum range.
- Current traces use up to 2500 time bins: the line shows each bin's mean and the shaded band its minimum–maximum range. Calculations use all samples. The band is not SD or measurement uncertainty. SVG plots can be enlarged without losing sharpness; individual raw samples remain in CSV files.
- Current and comparison plots show the trace from 0.2 s onward on the left and power-on startup (0–0.2 s) on the right, using raw samples. Both panels use their own axis scales; summary statistics still cover the full selected analysis window, including startup when selected.
- Individual current plots mark each panel's raw minimum in blue and maximum in orange. Comparison plots list each repeat's raw range below the panels and highlight the series extrema there, including tied results; the traces have no extrema annotations.
- Statistics plots list each repeat's mean current and total estimated energy below their respective panels. Blue and orange highlights identify the smallest and largest repeat results, not individual sample extremes. Coloured repeat keys appear in these lists without a duplicate legend.
- Complete task cycles are not detected automatically. Fixed-duration windows can contain different numbers of cycles.
- Calibration/resynchronization during acquisition invalidates the repeat; raw data are retained.

## Check without hardware

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
.\.venv\Scripts\python.exe -m src.stlink_measure demo
```

Demo creates **synthetic data** in `demo_results/`.
