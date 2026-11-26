# Output files

[Quick Start](../README.md#quick-start) · [Methodology](methodology.md) · [Plot interpretation](interpretation.md)

**One command = one run directory:** `results/<name>_<date>_<time>/`.

| Location / file | Contents |
| --- | --- |
| `repeat_001/` … `repeat_010/` | Raw `samples.csv`, received `stream.bin`, metadata, command log, analysis, and individual current plot |
| `comparison_eng.*` | All repeat traces, with matching repeat colors |
| `statistics_eng.*` | Individual repeat results, mean ± SD, and numerical summaries |
| `runs_summary.csv`, `statistics.csv` | Per-repeat and aggregate results |
| `session_config.json`, `warmup.json` | Setup and warm-up temperatures |
| `excluded_runs.json` | Excluded measurements and reasons |

Plots are saved as PNG and SVG. CSV uses semicolons and decimal points. New result directories are ignored by Git; the documented [baseline dataset](../firmware/nodemcu_led_cycles/README.md) is explicitly included. Back up raw measurements separately.

## Optional controller output

When `--controller` is used, each repeat also contains `controller.log` (stdout/stderr) and the `controller.stop` shutdown marker. Controller-specific files, such as `controller_events.csv`, are written by the controller itself; its result is recorded in `metadata.json`.

## Recreate reports

Run from the repository root; replace the example path with your saved session:

```powershell
.\.venv\Scripts\python.exe -m src.stlink_measure analyze --root results/no_code_20261114_183000_123456
```

Append `--from-s 4 --to-s 8` to select a time window. Reports and plots are regenerated; raw sample CSV files are preserved.
