# Extended planted-bug evaluation: from one case to five

This extends the single planted-bug experiment in Section 6.5 of the paper (the quantile-filter case) to five distinct bug categories: **filter, join, encoding, target leakage, and type coercion**. The goal is to move the diagnosis evidence from an anecdote (n=1) to a small controlled study (n=5) that shows both where the analyzer succeeds and where it does not.

All numbers below were produced by running the current `main` (the v0.7.0 development line, 240 hooks: pandas + scikit-learn; PySpark not installed in this run) on pandas 3.0.5 and scikit-learn 1.9.1. The scripts are in `benchmarks/planted_bugs/` and reproduce every figure with `bash run_all.sh`. The previous published run (AutoLineage 0.6.2, pandas 2.x) is kept in the "Before" column so the change is visible.

## Method

For each bug category I use one pipeline and change exactly one line between the healthy and the buggy version, holding everything else fixed. The protocol matches the paper:

1. Run the healthy pipeline, save a baseline fingerprint (`LineageAnalyzer.save_fingerprint`).
2. Run the buggy pipeline in a fresh process, load the baseline (`load_baseline`), then call `detect_anomalies()` and `localize_root_cause("f1_score")`.
3. Record whether the correct operation is flagged and its impact score.

The data is synthetic (6,000 rows, an amount feature, a categorical region, and a label concentrated in high-amount rows) so that each bug can be injected cleanly and reproducibly. The two real datasets from the paper, Credit Card Fraud and UCI Online Retail, remain the headline cases; this study is about controlled coverage across bug *types*, not dataset realism.

Two honest notes on construction. First, my first harness silently dropped every one-hot column because pandas 2.x returns boolean dummies and `select_dtypes(include=[number])` excludes booleans. That is itself exactly the class of silent structural bug this tool targets, and it is fixed in the released scripts (dummies are cast to float). Second, the same harness crashed on pandas 3.0 because string columns are now `str` dtype, not `object`, so the `dtype == object` filter that removed them no longer matched and `StandardScaler` received text. The scripts now drop columns with `not pd.api.types.is_numeric_dtype(...)`, which is what the filter meant all along. I mention both because they are good reminders that these bugs are easy to write by accident.

## Results

| # | Bug category | The one-line change | Baseline F1 | Buggy F1 | Detected | Localized operation (impact) | Verdict | Before (0.6.2) |
|---|---|---|---|---|---|---|---|---|
| 1 | Filter | `quantile(0.999)` to `quantile(0.05)` | 0.828 | **0.000** | yes (critical) | `filter` (1.0) | exact | `filter` (1.0), exact |
| 2 | Join fan-out | merge key `["region","tier"]` to `["region"]` | 0.837 | 0.837 | yes | `merge` (1.0) | exact | `merge` (0.8), exact |
| 3 | Encoding blow-up | one-hot `region` to `customer_id` (+396 cols) | 0.836 | 0.738 | yes (critical) | `get_dummies` (1.0) | **exact** | `drop` (0.3), proximate |
| 4 | Target leakage | drop label `y` from X, versus keep it | 0.836 | **1.000** | yes (critical) | `get_dummies` (0.7), names `y` | **exact** | `drop` (0.3), proximate |
| 5 | Type coercion | `to_numeric(errors="raise")` to `"coerce"` + `dropna` | 0.834 | 0.840 | yes | `dropna` (0.5) | exact | `dropna` (0.5), exact |

**Detection: 5 / 5.** Every planted bug produced a critical or warning anomaly pinpointing the region of the pipeline that changed.

**Exact-operation localization: 5 / 5.** In every case the analyzer named the operation the bug lived in. For the two cases that were proximate in 0.6.2 it now also names the columns:

- *Encoding* — `get_dummies` at step 0: "introduced 399 column(s) the baseline never saw: customer_id_1, customer_id_10, ... (+394 more). 3 column(s) it created in the baseline were never created: region_north, region_south, region_west."
- *Leakage* — `get_dummies` at step 0: "Column(s) y were removed by drop in the baseline but are never removed in this run." The bug here is a *missing* operation, so there is no literal buggy call to point at; the analyzer instead names the leaked column and the step at which it entered the feature frame, which is the diagnosis a developer needs.

Two things changed between 0.6.2 and this run. `pd.get_dummies` is now a hooked operation with its own lineage record, so an encoding change is visible where it happens rather than one step downstream. And the fingerprint now carries column *sets* per operation (output columns, columns added, columns removed, every column seen), not just column counts. The analyzer uses them for three attributions, each credited to a single operation so that downstream operations that merely inherit the changed column set are not blamed: columns the baseline never saw (*introduced*), columns the baseline deliberately removed that this run never removes (*retained*, the leakage signature), and columns the baseline created that this run never creates (*missing*). Each contributes 0.4 to the localization score at its origin operation.

## Across seeds (0–4)

The table above is seed 0. `run_seeds.py` reruns every case with seeds 0–4; the seed controls the synthetic data, the train/test split and the sampling step, so each seed is a different 6,000-row dataset with the same one-line bug. Twenty-five healthy/buggy pairs, each in fresh processes:

| # | Bug category | Baseline F1 (mean ± sd) | Buggy F1 (mean ± sd) | Detected | Exact localization | Impact (mean ± sd) |
|---|---|---|---|---|---|---|
| 1 | Filter | 0.843 ± 0.014 | 0.000 ± 0.000 | 5/5 | 5/5 | 1.00 ± 0.00 |
| 2 | Join fan-out | 0.841 ± 0.008 | 0.847 ± 0.015 | 5/5 | 5/5 | 1.00 ± 0.00 |
| 3 | Encoding blow-up | 0.843 ± 0.009 | 0.723 ± 0.019 | 5/5 | 5/5 | 1.00 ± 0.00 |
| 4 | Target leakage | 0.843 ± 0.009 | 1.000 ± 0.000 | 5/5 | 5/5 | 0.70 ± 0.00 |
| 5 | Type coercion | 0.844 ± 0.010 | 0.843 ± 0.006 | 5/5 | 5/5 | 0.50 ± 0.00 |

**Detection 25/25, exact localization 25/25.** Per-run results are in `results_multiseed.json`.

What this does and does not show. The metric effects vary with the data as expected (encoding F1 0.70–0.75 across seeds), but the localized operation and its impact score did not change on any seed. That is because these bugs are large structural changes (a filter keeping 5% of rows, a 6,000-row join fan-out, 399 extra columns) that dwarf seed-to-seed noise, so the result says the localization is stable under resampling, not that it holds for subtle bugs. Varying bug *severity* (how many rows a filter drops, how many columns an encoding adds) is the next axis to test, and is where a lower impact score would start to compete with noise.

## What the five cases show

The three row-count bugs (filter, join, type) localize on row-count deviation, which carries the largest weight in the scoring (0.6, versus 0.4 for a column-set change at its origin, 0.3 for a column-count change, and 0.1 for a new operation). The two column bugs (encoding, leakage) now localize on column-set membership: the count change alone (0.3) is inherited by every operation downstream and ties them, while the membership change is attributed to one operation and breaks the tie. The leakage case scores 0.7 rather than 1.0 because a single retained column is, by design, weaker evidence than a 399-column blow-up; it still wins by a clear margin over the next candidate (0.3).

Two cases moved the metric dramatically and two barely moved it. Filter drove F1 to 0.000; leakage drove it to a suspicious 1.000, which is the classic leak signature a reviewer would want flagged. Join and type changed F1 by less than a point, yet the analyzer still caught the structural drift (a 6,000-row join fan-out, a 2,400-row silent drop from coercion). This is the intended value: the tool reports what the code did to the data even when the headline metric has not yet visibly moved, which is precisely when these bugs are most dangerous.

## Honest limitations of this study

- **Synthetic data.** Controlled injection is a feature here, but it is not a substitute for real-world bug corpora. A stronger future version would mine real regressions or use a public bug benchmark.
- **Localization quality depends on which operations are hooked.** The 0.6.2 run localized two of five cases to a neighbour because `get_dummies` was not hooked; adding the hook fixed both. The same gap exists for any column-producing call that is not yet instrumented (e.g. `pd.cut`, `str.get_dummies`, `pd.crosstab`): its effect still surfaces one step downstream.
- **Membership attribution assumes column names are stable.** A run that renames columns (`rename`, prefix changes) will report the renamed columns as introduced and the old names as missing at the rename step, which is correct but noisier than a count-only comparison.
- **Shape-preserving semantic bugs remain out of scope.** Every bug here changes a row or column count. A unit error that scales a column by 1000 while preserving all shapes would still slip through, exactly as the paper states.
- **Seeds vary the data, not the bug.** Five seeds per case (above) show the localization is stable under resampling; bug severity is fixed per case, so how small a bug can be and still be localized is untested.

## Reproducibility

```
cd benchmarks/planted_bugs
pip install "autolineage[sklearn]" scikit-learn pandas numpy
bash run_all.sh          # seed 0, the table above
python run_seeds.py      # seeds 0-4, the across-seeds table (about a minute)
```

Each case prints the baseline F1, the buggy F1, the ranked anomalies, and the localized root cause with its impact score.

## Determinism

Random seeds are fixed for data generation, the train/test split, and the sampling step,
and the classifier is deterministic, so the reported metrics (baseline and buggy F1) and
the localized operation reproduce exactly across runs. `PYTHONHASHSEED` is pinned in
`run_all.sh` for stable ordering. The *total anomaly count* can vary by one or two between
runs because it includes timing-sensitive signals; the localization result does not depend
on them.
