# Onboarding

About ten minutes. This is for a data engineer who has not seen the project before. AutoLineage is research-stage software. It records pandas, scikit-learn, and PySpark operations in one process. Polars is not tracked yet.

## Install

Use Python 3.10 or newer.

```bash
pip install "autolineage[sklearn]"
```

The base install always brings pandas. The `sklearn` extra also installs scikit-learn. PySpark is tracked when that package is installed (`pip install "autolineage[pyspark]"`).

## One example

`examples/pipeline.py` trains a random forest on the Wisconsin breast cancer dataset that ships with scikit-learn. No extra download.

```bash
python examples/pipeline.py
```

One run of that script with AutoLineage 0.8.1, Python 3.12, on 21 November 2026 printed:

```
AutoLineage: 305 hooks installed across 3 frameworks (pandas-io, pandas-transforms, sklearn)
F1 = 0.9693
<UnifiedTracker: 11 operations across pandas-transforms, sklearn>
wrote trace.html  (open it in a browser)
```

`trace.html` is the lineage graph. Click a node for the operation, the row counts, and the upstream steps. Running those same calls recorded, in order: `concat`, `filter`, `select`, `dropna`, `filter`, `drop`, `train_test_split`, `RandomForestClassifier.__init__`, `RandomForestClassifier.fit`, `RandomForestClassifier.predict`, `f1_score`. The first three come from `load_breast_cancer(as_frame=True)`, not from lines in the example.

This is one run, not a benchmark.

## What a check looks like

Save a run, change the script, and compare:

```bash
autolineage baseline examples/pipeline.py -o baseline.json
autolineage check examples/pipeline.py --baseline baseline.json
```

Exit code 0 means the checks passed. Exit code 1 means a check failed. Exit code 2 means the script failed or nothing was recorded.

A second run of the same dataset with the filter `mean radius < 10` instead of `mean radius < 25` reported:

```
[critical] filter row change: -522 (baseline: -5, 10340% deviation)
```

The recorded F1 rose on that run (0.9693 to 1.0000), so `localize_root_cause("f1_score")` returned no cause. Localization names an operation when a recorded metric falls. The explanation names the operation and the step, for example a filter whose row change is the one tied to the metric drop.

## Report a silent failure

A silent failure is a pipeline that finished without an exception and still produced the wrong rows, keys, or metric. Open a [silent-failure report](../.github/ISSUE_TEMPLATE/silent_failure.md) and include:

- the pipeline (repository, script, or a minimal script)
- the framework (pandas, scikit-learn, PySpark)
- what ran fine (the command finished, the exit code, the metric or row count you expected)
- what was wrong

Do not include private data or credentials. A bug in AutoLineage itself goes in the bug report. A request for a new framework or check goes in the feature request.
