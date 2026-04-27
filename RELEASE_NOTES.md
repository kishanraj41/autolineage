# AutoLineage v0.4.0

**Interactive visualization + automated diagnosis on lineage graphs.**

This release moves AutoLineage beyond *capturing* lineage into *acting* on it: detecting anomalies against a saved baseline, localizing root causes when metrics degrade, and rendering everything as an interactive graph. Every change is backed by tests; every paper claim is backed by reproducible measurements.

```bash
pip install --upgrade autolineage
```

---

## Highlights

### Interactive lineage visualization

`tracker.visualize()` opens a self-contained HTML page in your browser with pan, zoom, click-to-inspect, and upstream highlighting. No external dependencies — no Graphviz install required.

```python
import autolineage.auto
import pandas as pd

df = pd.read_csv("data.csv").dropna()
df = df[df["amount"] > 0]
df = df.assign(log_amount=df["amount"].apply(np.log1p))

from autolineage.auto import get_tracker
get_tracker().visualize()                  # opens HTML in browser
get_tracker().to_dot()                     # Graphviz DOT
get_tracker().to_mermaid()                 # Markdown-friendly Mermaid
```

In Jupyter notebooks, putting the tracker as the last expression in a cell auto-renders a summary table — no explicit print needed.

### Anomaly detection against a saved baseline

```python
from autolineage.core.analyzer import LineageAnalyzer

# After a healthy run
analyzer = LineageAnalyzer(tracker)
analyzer.save_fingerprint("baseline.json")

# In a future run
analyzer = LineageAnalyzer(new_tracker)
analyzer.load_baseline("baseline.json")
for a in analyzer.detect_anomalies():
    print(f"[{a.severity}] {a.message}")
# [critical] filter row change: -47,500 (baseline: -50, 94900% deviation)
# [critical] f1_score dropped from 0.9842 to 0.0000 (-100.0%)
```

### Root-cause localization

When a metric degrades, the analyzer walks the DAG and identifies which operation is most likely responsible:

```python
cause = analyzer.localize_root_cause("f1_score")
print(cause.explanation)
# "The most likely cause of f1_score degradation (from 0.9842 to 0.0000)
#  is 'filter' at step 5. Row change was -47,500 (baseline: -50)."
```

Run the end-to-end demo to see this in action:

```bash
python examples/anomaly_demo.py
```

### Early-import gotcha detection

The most common AutoLineage user mistake is writing `from sklearn.metrics import f1_score` *before* `import autolineage.auto`. The local reference then bypasses the wrapper and metrics aren't tracked — silently. v0.4.0 detects this case at hook-installation time and emits a `UserWarning` pointing at the specific shadowed symbol with concrete remediation guidance.

---

## What's New (Detailed)

### Added

- **`autolineage/viz.py`** — visualization module producing interactive HTML, Graphviz DOT, and Mermaid output. Self-contained, zero runtime dependencies.
- **`UnifiedTracker.visualize()`**, **`.to_dot()`**, **`.to_mermaid()`** — first-class export methods on the tracker.
- **`UnifiedTracker._repr_html_()`** — Jupyter rich output. Drop the tracker as the last expression in a cell and a summary table renders inline.
- **`LineageAnalyzer.detect_anomalies()`** — promoted from preliminary to first-class. Three severity levels (critical, warning, info), configurable thresholds, fallback to self-anomaly mode when no baseline exists.
- **`LineageAnalyzer.localize_root_cause(metric_name)`** — deviation-weighted DAG walk that returns a structured `RootCause` with explanation, impact score, and supporting evidence.
- **`LineageAnalyzer.save_fingerprint()`** / **`.load_baseline()`** — persist run fingerprints across processes for cross-run anomaly detection.
- **`examples/anomaly_demo.py`** — end-to-end planted-bug demo showing baseline → buggy run → critical alerts → root cause output. Reproducible in 30 seconds on any machine.
- **Early-import detection** — `_warn_about_early_metric_imports()` scans `__main__` after hook installation for sklearn metric references that bypass the wrapper.
- **Three new figures in the paper** including a per-category hook breakdown (Table 2), the 37 → 24 operations reconciliation (Table 4), and a lineage DAG visualization (Figure 2).

### Fixed

- **Edge resolution for pandas reassignment chains.** The previous `child_to_idx` dict was clobbered when records shared `child_id` (the common pandas pattern of reassigning to `df`), producing backward edges and misordered layouts. Now resolves edges chronologically using `child_to_indices` with a sequential fallback.
- **Cleaned up `auto.py`** — removed dead imports referencing the legacy `tracker.py` / `database.py` modules from the pre-v0.3.0 architecture.

### Tests

- **51 tests passing**, up from 36 in v0.3.0.
  - 12 new tests covering visualization output (HTML, DOT, Mermaid, empty tracker)
  - 3 regression tests on edge resolution (linear chain, upstream traversal, layer assignment)
  - 1 test verifying the early-import warning fires correctly
  - 4 tests for Jupyter rich output

### Paper

The v4 manuscript (`paper/autolineage.tex`) addresses every concern raised in the previous review round:

- Hook counts synced to released code (64 / 175 / 49) throughout
- New §5.6 documenting the early-import failure mode and its mitigation
- New §6 (six subsections) on Automated Diagnosis on Lineage Graphs, with run fingerprinting, anomaly detection algorithm, root-cause localization algorithm, and a complete planted-bug experiment
- §6.2 reconciles the 37 listed steps with 24 captured operations via a new explanatory table
- §7 (Threats to Validity) expanded from 3 to 4 fragility points; adds GC discussion and mechanized-proof gap
- Real reproducibility commands with pinned versions (§6.5)
- All performance numbers backed by raw CSV data committed to the repo (`paper/microbench_v2_results.csv`, `paper/scaling_results.csv`)

---

## Performance

Per-operation instrumentation cost on a 37-operation pipeline (Intel i7-12700H, Python 3.12, pandas 3.0):

| Condition | Mean per call | 95% CI |
|---|---|---|
| Baseline | 263.5 µs | ± 8.8 µs |
| With AutoLineage | 348.2 µs | ± 9.0 µs |
| **Overhead** | **84.7 µs / op** | **[78, 91]** |

At production data scales (≥10⁵ rows), end-to-end overhead becomes indistinguishable from baseline variance because framework computation dominates wall-clock time. Full scaling study from 10³ to 10⁶ rows in `paper/scaling_results.csv`.

---

## Upgrade Notes

This release is fully backward-compatible with v0.3.0. The `import autolineage.auto` entry point and the `UnifiedTracker` API are unchanged. New methods (`visualize`, `to_dot`, `to_mermaid`, `_repr_html_`) are additive.

If you were using the `LineageAnalyzer` API in v0.3.0, the `detect_anomalies()` and `localize_root_cause()` methods have been finalized — earlier preview signatures are no longer guaranteed compatible.

---

## What's Next

The next release will focus on:

- **OpenTelemetry export** — addresses the single-process limitation by enabling cross-machine lineage stitching
- **Additional framework support** — Polars, XGBoost, LightGBM (each ~200 LoC under the existing plugin architecture)
- **A formal user study** measuring debugging-time reduction on real-world pipelines

The supporting research paper will be made available on arXiv. The README citation block will be updated with the arXiv ID once approved.

---

## Acknowledgments

Thanks to everyone who has filed issues, opened PRs, or just tried the tool. Bug reports and feedback at <https://github.com/kishanraj41/autolineage/issues> are very welcome.

If AutoLineage helps you ship better ML pipelines, consider starring the repository — it helps others discover the project.

---

## Citation

```bibtex
@misc{vandhavasi2026autolineage,
  title={AutoLineage: Operation-Level Data Lineage for Python ML Pipelines via Import-Time Hooking},
  author={Vandhavasi, Kishan Raj},
  year={2026},
  eprint={2604.XXXXX},
  archivePrefix={arXiv},
  primaryClass={cs.SE}
}
```

> The arXiv ID will be filled in once the preprint is approved.