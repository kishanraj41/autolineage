# Extended planted-bug evaluation: from one case to five

This extends the single planted-bug experiment in Section 6.5 of the paper (the quantile-filter case) to five distinct bug categories: **filter, join, encoding, target leakage, and type coercion**. The goal is to move the diagnosis evidence from an anecdote (n=1) to a small controlled study (n=5) that shows both where the analyzer succeeds and where it does not.

All numbers below were produced by running AutoLineage 0.6.2 (code identical to 0.6.1; 239 hooks: pandas + scikit-learn; PySpark not installed in this run). The scripts are in `benchmarks/planted_bugs/` and reproduce every figure with `bash run_all.sh`.

## Method

For each bug category I use one pipeline and change exactly one line between the healthy and the buggy version, holding everything else fixed. The protocol matches the paper:

1. Run the healthy pipeline, save a baseline fingerprint (`LineageAnalyzer.save_fingerprint`).
2. Run the buggy pipeline in a fresh process, load the baseline (`load_baseline`), then call `detect_anomalies()` and `localize_root_cause("f1_score")`.
3. Record whether the correct operation is flagged and its impact score.

The data is synthetic (6,000 rows, an amount feature, a categorical region, and a label concentrated in high-amount rows) so that each bug can be injected cleanly and reproducibly. The two real datasets from the paper, Credit Card Fraud and UCI Online Retail, remain the headline cases; this study is about controlled coverage across bug *types*, not dataset realism.

One honest note on construction: my first harness silently dropped every one-hot column because pandas 2.x returns boolean dummies and `select_dtypes(include=[number])` excludes booleans. That is itself exactly the class of silent structural bug this tool targets, and it is fixed in the released scripts (dummies are cast to float). I mention it because it is a good reminder that these bugs are easy to write by accident.

## Results

| # | Bug category | The one-line change | Baseline F1 | Buggy F1 | Detected | Localized operation (impact) | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Filter | `quantile(0.999)` to `quantile(0.05)` | 0.828 | **0.000** | yes (critical) | `filter` (1.0) | exact |
| 2 | Join fan-out | merge key `["region","tier"]` to `["region"]` | 0.837 | 0.837 | yes | `merge` (0.8) | exact |
| 3 | Encoding blow-up | one-hot `region` to `customer_id` (+396 cols) | 0.836 | 0.738 | yes | `drop` (0.3) | proximate |
| 4 | Target leakage | drop label `y` from X, versus keep it | 0.836 | **1.000** | yes | `drop` (0.3) | proximate |
| 5 | Type coercion | `to_numeric(errors="raise")` to `"coerce"` + `dropna` | 0.834 | 0.840 | yes | `dropna` (0.5) | exact |

**Detection: 5 / 5.** Every planted bug produced a critical or warning anomaly pinpointing the region of the pipeline that changed.

**Exact-operation localization: 3 / 5** (filter, join, type). In these cases the analyzer named the precise operation the bug lived in.

**Proximate localization: 2 / 5** (encoding, leakage). Here the analyzer flagged the correct structural symptom (a column-count change of +396 for the encoding blow-up, and the extra label column for leakage) but attributed it to the adjacent recorded operation (`drop`) rather than the literal buggy call. The reason is concrete and fixable: `pd.get_dummies` and "forgetting to drop the label" are not separately hooked operations, so the column-count change first becomes visible at the next instrumented step. Hooking `get_dummies` and column-set membership would convert both of these from proximate to exact.

## What the five cases show

The three cases that localize exactly (filter, join, type) are all **row-count** bugs, and row-count deviation carries the largest weight in the scoring (0.6, versus 0.3 for column count and 0.1 for novelty). That is why they also earn the highest impact scores. The two proximate cases are **column-count** bugs, which by design score lower (0.3) and, in this build, surface one operation downstream of their true origin.

Two cases moved the metric dramatically and two barely moved it. Filter drove F1 to 0.000; leakage drove it to a suspicious 1.000, which is the classic leak signature a reviewer would want flagged. Join and type changed F1 by less than a point, yet the analyzer still caught the structural drift (a 6,000-row join fan-out, a 2,400-row silent drop from coercion). This is the intended value: the tool reports what the code did to the data even when the headline metric has not yet visibly moved, which is precisely when these bugs are most dangerous.

## Honest limitations of this study

- **Synthetic data.** Controlled injection is a feature here, but it is not a substitute for real-world bug corpora. A stronger future version would mine real regressions or use a public bug benchmark.
- **Two of five localize to a neighbor, not the exact line.** This is a real gap driven by unhooked operations (`get_dummies`, label handling), not a fundamental limit. It is the clearest next engineering task.
- **Shape-preserving semantic bugs remain out of scope.** Every bug here changes a row or column count. A unit error that scales a column by 1000 while preserving all shapes would still slip through, exactly as the paper states.
- **Single random seed per case.** The scripts fix `seed=0`; a fuller evaluation would report variance across seeds.

## Reproducibility

```
cd benchmarks/planted_bugs
pip install "autolineage[sklearn]" scikit-learn pandas numpy
bash run_all.sh
```

Each case prints the baseline F1, the buggy F1, the ranked anomalies, and the localized root cause with its impact score.

## Determinism

Random seeds are fixed for data generation, the train/test split, and the sampling step,
and the classifier is deterministic, so the reported metrics (baseline and buggy F1) and
the localized operation reproduce exactly across runs. `PYTHONHASHSEED` is pinned in
`run_all.sh` for stable ordering. The *total anomaly count* can vary by one or two between
runs because it includes timing-sensitive signals; the localization result does not depend
on them.
