# AutoLineage

**Zero-code data lineage for Python ML pipelines.**

AutoLineage automatically records every DataFrame operation, model training step, and metric evaluation across pandas, scikit-learn, and PySpark. One `import` activates 288 hooks. No decorators, no wrapper classes, no configuration files.

```python
import autolineage.auto        # that's the whole setup

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score

df = pd.read_csv("data.csv")
df = df.dropna()
X, y = df.drop(columns=['target']), df['target']

model = RandomForestClassifier().fit(X, y)
preds = model.predict(X_test)
score = f1_score(y_test, preds)

# AutoLineage has now tracked every operation above into one unified DAG.
```

---

## Why AutoLineage?

ML pipelines fail silently. A model whose F1 drops from 0.95 to 0.60 invites hours of `print(df.shape)` debugging. Existing tools either require explicit instrumentation (MLflow), track only files (DVC), or cover only a single stage (Evidently, Arize). **No existing tool records the complete path from `read_csv` through `f1_score` in one graph automatically.**

AutoLineage closes that gap.

### Compared to other tools

| Capability | AutoLineage | MLflow | Evidently | OpenLineage | DataLineagePy |
|---|---|---|---|---|---|
| Zero code changes | **Yes** | No | No | No | No (wrapper) |
| Operation-level | **Yes** | No | No | Job-level | Yes |
| Cross-framework | **pandas + sklearn + PySpark** | — | — | Spark only | pandas only |
| End-to-end trace | **Yes** | No | No | No | No |
| Anomaly detection | **Yes** | No | Drift only | No | No |
| Root-cause localization | **Yes** | No | No | No | No |

---

## Installation

```bash
pip install autolineage
```

---

## Quick Start

### 1. Automatic tracking (one line)

```python
import autolineage.auto

# Use pandas and sklearn normally
import pandas as pd
df = pd.read_csv("iris.csv")
df = df.dropna().drop_duplicates()

# See what happened
from autolineage.auto import get_tracker
tracker = get_tracker()
for rec in tracker.records:
    print(f"{rec.operation}: {rec.input_shape} -> {rec.output_shape}")
```

### 2. Anomaly detection

```python
from autolineage.core.analyzer import LineageAnalyzer

analyzer = LineageAnalyzer(tracker)
anomalies = analyzer.detect_anomalies()

for a in anomalies:
    print(f"[{a.severity}] {a.message}")
# [critical] filter removed 99.9% of rows (100000 -> 50)
# [critical] f1_score = 0.0 (model may not be learning)
```

### 3. Root-cause localization

```python
cause = analyzer.localize_root_cause(metric_name="accuracy")
print(cause.explanation)
# "The most likely cause of accuracy degradation is 'filter' at step 3.
#  Row change was -99,950 (baseline: -2,100)."
```

### 4. Save a fingerprint for future comparison

```python
# After a healthy run
analyzer.save_fingerprint("baseline.json")

# On the next run
analyzer.load_baseline("baseline.json")
anomalies = analyzer.detect_anomalies()  # compared to baseline
```

---

## What Gets Tracked

**pandas (64 hooks):** `read_csv`, `to_csv`, `dropna`, `fillna`, `merge`, `concat`, `groupby` + aggregations, `drop_duplicates`, `filter`, `assign`, `sort_values`, `pivot_table`, `melt`, plus 40+ more.

**scikit-learn (175 hooks):** `train_test_split`, estimator `fit`/`predict`/`predict_proba`/`score` (RandomForest, LogisticRegression, DecisionTree, SVC, KNN, etc.), 18 preprocessor classes, 15 metric functions.

**PySpark (49 hooks):** DataFrame transforms, groupBy aggregations, join variants, reader/writer methods, actions.

---

## Example Output

On a 284K-row credit card fraud detection pipeline:

```
 1. [io        ] read_csv -> (284807, 31)                    [1280ms]
 2. [transform ] drop_duplicates (-1,081 rows)                [827ms]
 3. [transform ] filter (-284 rows)
 4. [transform ] assign -> 36 cols                              [1ms]
 5. [transform ] select -> 34 cols
 6. [split     ] train_test_split (80/20)                     [218ms]
 7. [preprocess] StandardScaler.fit_transform                 [201ms]
 8. [preprocess] StandardScaler.transform                      [17ms]
 9. [train     ] RandomForestClassifier.fit                 [88637ms]
10. [train     ] LogisticRegression.fit                      [1138ms]
11. [predict   ] RandomForestClassifier.predict               [332ms]
12. [predict   ] LogisticRegression.predict                     [4ms]
13. [predict   ] RandomForestClassifier.predict_proba         [311ms]
14. [evaluate  ] accuracy_score = 0.9995
15. [evaluate  ] precision_score = 0.8824
16. [evaluate  ] recall_score = 0.7895
17. [evaluate  ] f1_score = 0.8333
18. [evaluate  ] roc_auc_score = 0.9871
```

24 clean records. Zero noise. End-to-end trace from CSV to metrics.

---

## Architecture

Plugin-based. Each library is a single file implementing `BaseHookProvider`. Adding new libraries requires ~200 lines and zero changes to the core.

```
User Code (unchanged)
        |
Hook Providers (pandas | sklearn | pyspark | ...)
        |
UnifiedTracker + TransformationRecord
        |
LineageAnalyzer -> anomalies, root causes, DAGs
```

---

## Performance

Benchmarked on a 37-operation pipeline (50K rows, pandas + sklearn):

| Condition | Wall time |
|---|---|
| Without AutoLineage | 0.050s |
| With AutoLineage | 0.054s |
| **Overhead** | **6.1% (0.08ms per operation)** |

---

## Limitations

- **Single-process.** Pipelines spanning multiple machines require manual trace correlation. OpenTelemetry export is planned.
- **Monkey-patching is version-sensitive.** Tested against pandas 2.x/3.x, scikit-learn 1.x, PySpark 3.x/4.x.
- **Python-only.** R, Julia, Java are out of scope.
- **In-memory records.** Long notebook sessions accumulate state.

---

## Contributing

Add a new library in 5 steps:

1. Create `autolineage/hooks/your_lib_hooks.py`
2. Subclass `BaseHookProvider`
3. Implement `install(tracker)` and `uninstall()`
4. Add to the registry in `hooks/registry.py`
5. Open a PR

See `hooks/pandas_io.py` for the smallest working example (~110 LoC).

---

## Development

```bash
git clone https://github.com/kishanraj41/autolineage
cd autolineage
pip install -e ".[dev]"
pytest tests/test_v2.py -v     # 36 tests
```

---

## License

MIT

---

## Citation

```bibtex
@misc{vandhavasi2026autolineage,
  title={AutoLineage: Zero-Code End-to-End Data Lineage for ML Pipelines},
  author={Vandhavasi, Kishan Raj},
  year={2026},
  archivePrefix={arXiv},
  primaryClass={cs.SE}
}
```
