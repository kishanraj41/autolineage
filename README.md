# AutoLineage

**Automatic ML Data Lineage Tracking**

Track every transformation in your ML pipeline — from raw data to trained model — without changing a single line of code.

[![PyPI](https://img.shields.io/pypi/v/autolineage.svg)](https://pypi.org/project/autolineage/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-34%20passing-brightgreen.svg)]()

## The Problem

You run an ML pipeline. Months later, someone asks: *"What transformations were applied to this data? Which rows were dropped? What columns were engineered?"*

Existing tools (MLflow, DVC) require you to manually log everything or restructure your code around their framework. Most practitioners don't bother — and lineage is lost.

## The Solution

```python
import autolineage.auto  # ← Add this one line. That's it.

import pandas as pd

df = pd.read_csv("housing.csv")           # Tracked: file read, schema captured
df_clean = df.dropna()                      # Tracked: 207 rows removed
df_feat = df_clean.assign(                  # Tracked: 3 columns added
    rooms_per_house=lambda x: x["total_rooms"] / x["households"],
    bedrooms_ratio=lambda x: x["total_bedrooms"] / x["total_rooms"],
    log_income=lambda x: np.log1p(x["median_income"]),
)
df_feat.to_csv("features.csv")             # Tracked: file write, linked to lineage
```

Every operation is recorded automatically: what changed, how many rows/columns were affected, and the full parent-child chain from source to output.

## Sample Output

Running the [California Housing demo pipeline](examples/california_housing_pipeline.py) produces this lineage automatically:

```
  AUTOLINEAGE TRACKING SUMMARY
  ============================================================
  DataFrames tracked:    25+
  Transformations:       15+
  Rows filtered:         4,000+
  Column changes:        20+

  Operations breakdown:
    assign                        4x
    filter                        4x
    select_columns                2x
    dropna                        1x
    query                         1x

  COMPLETE DATA LINEAGE
  ============================================================
    1. dropna          [(20640, 10) → (20433, 10)]  rows:20640→20433
    2. query           [(20433, 10) → (20433, 10)]
    3. filter          [(20433, 10) → (16512, 10)]  rows:20433→16512
    4. assign          [(16512, 10) → (16512, 13)]  +cols:['bedrooms_per_room', 'population_per_household', 'rooms_per_household']
    5. assign          [(16512, 13) → (16512, 16)]  +cols:['log_income', 'log_population', 'log_total_rooms']
    6. assign          [(16512, 16) → (16512, 17)]  +cols:['lat_bin']
    7. assign          [(16512, 17) → (16512, 18)]  +cols:['age_category']
    8. select_columns  [(16512, 18) → (16512, 14)]  -cols:['age_category', 'lat_bin', 'median_house_value', 'ocean_proximity']
    9. select_columns  [(16512, 18) → (16512, 1)]
   10. filter          [(16512, 14) → (13255, 14)]  rows:16512→13255  (train split)
   11. filter          [(16512, 14) → (3257, 14)]   rows:16512→3257   (test split)
   12. assign          [(3257, 14) → (3257, 18)]    +cols:['abs_error', 'actual', 'predicted', 'residual']

  File → DataFrame mappings:
    housing.csv              → source DataFrame
    02_cleaned_data.csv      → after dropna + outlier removal
    03_features.csv          → after feature engineering
    04_X_train.csv           → training features
    06_predictions.csv       → model predictions with residuals
```

Every step is captured: which rows were dropped, which columns were added or removed, and the shape changes at each transformation.

## Installation

```bash
pip install autolineage
```

## What Gets Tracked

### File I/O (automatic)

| Library | Read | Write |
|---------|------|-------|
| **pandas** | `read_csv`, `read_parquet`, `read_json`, `read_excel`, `read_pickle` | `to_csv`, `to_parquet`, `to_json`, `to_excel`, `to_pickle` |
| **numpy** | `load`, `loadtxt` | `save`, `savetxt` |
| **pickle** | `load` | `dump` |
| **joblib** | `load` | `dump` |

### In-Memory Transformations (automatic)

| Category | Operations Tracked |
|----------|--------------------|
| **Cleaning** | `dropna`, `fillna`, `drop_duplicates`, `drop`, `replace`, `clip` |
| **Selection** | `df[columns]`, `df[mask]`, `query`, `head`, `tail`, `nlargest`, `nsmallest`, `sample` |
| **Reshaping** | `merge`, `concat`, `pivot_table`, `melt`, `explode`, `assign` |
| **Transformation** | `rename`, `astype`, `sort_values`, `reset_index`, `set_index`, `apply` |
| **Aggregation** | `groupby` + `sum`, `mean`, `median`, `std`, `count`, `min`, `max`, `agg`, `apply` |

For each operation, AutoLineage records:
- **Operation name and parameters**
- **Shape before → after**
- **Columns added / removed**
- **Rows before → after**
- **Content fingerprint**
- **Parent-child relationships**

## Performance

Benchmarked across 13 pandas operations at varying dataset sizes (10 runs each):

| Dataset Size | Avg Overhead | Relative Overhead |
|-------------|-------------|-------------------|
| 1,000 rows | ~1.1 ms | Negligible for interactive work |
| 10,000 rows | ~1.3 ms | Negligible for batch pipelines |
| 100,000 rows | ~4.3 ms | ~50% relative |
| 500,000 rows | ~12.8 ms | ~33% relative |

Overhead is dominated by a constant ~1ms per operation for metadata recording. As dataset size grows, the relative cost shrinks because pandas operations themselves take longer.

Full benchmark suite: [`benchmarks/benchmark_overhead.py`](benchmarks/benchmark_overhead.py)

## How It Works

AutoLineage uses **function hooking** (monkey-patching) to intercept pandas and numpy operations at runtime. When you call `df.dropna()`, AutoLineage's hook:

1. Calls the original `dropna()`
2. Records the input DataFrame's shape, columns, and lineage ID
3. Records the output DataFrame's shape and columns
4. Computes what changed (rows removed, columns added/dropped)
5. Stores the transformation as an edge in the lineage graph

No code changes. No decorators. No configuration files. Just `import autolineage.auto`.

```
housing.csv
    │
    ▼
[read_csv] → DataFrame(20640, 10)
    │
    ▼
[dropna] → DataFrame(20433, 10)     ← 207 rows removed
    │
    ▼
[query] → DataFrame(20433, 10)      ← outlier filter
    │
    ▼
[filter] → DataFrame(16512, 10)     ← capped values removed
    │
    ▼
[assign ×4] → DataFrame(16512, 18)  ← 8 engineered features
    │
    ├──[select_columns]──→ X (16512, 14)
    │                         │
    │                    ┌────┴────┐
    │                    ▼         ▼
    │              X_train    X_test
    │             (13255,14) (3257,14)
    │
    └──[select_columns]──→ y (16512, 1)
                              │
                         ┌────┴────┐
                         ▼         ▼
                   y_train    y_test
                  (13255,1)  (3257,1)
```

## How AutoLineage Compares

| Capability | AutoLineage | MLflow | DVC |
|-----------|------------|--------|-----|
| Setup required | `import autolineage.auto` | `mlflow.start_run()` + manual logging | `dvc.yaml` pipeline definition |
| In-memory transform tracking | ✅ Automatic | ❌ | ❌ |
| Column-level change detection | ✅ Automatic | ❌ | ❌ |
| Row-level change detection | ✅ Automatic | ❌ | ❌ |
| File I/O tracking | ✅ Automatic | ⚠️ Manual `log_artifact` | ✅ Via pipeline deps |
| Code changes required | None | Significant | Moderate |
| Pipeline orchestration | ❌ | ❌ | ✅ |
| Experiment tracking | ❌ | ✅ | ✅ |
| Data versioning | ❌ | ✅ | ✅ |

**AutoLineage is not a replacement for MLflow or DVC.** It solves a different problem: capturing what *actually happened* to your data at the operation level, automatically, without requiring you to restructure your workflow.

## Real-World Demo

See [`examples/california_housing_pipeline.py`](examples/california_housing_pipeline.py) for a complete ML pipeline:

```bash
# Download the dataset
mkdir -p examples/data
curl -o examples/data/housing.csv \
  https://raw.githubusercontent.com/ageron/handson-ml2/master/datasets/housing/housing.csv

# Run the pipeline
pip install autolineage scikit-learn
python examples/california_housing_pipeline.py
```

The pipeline runs a full workflow (load → clean → feature engineer → split → train → evaluate) and generates a complete lineage report in `demo_output/07_lineage.json`.

## CLI

```bash
lineage summary     # Show tracked datasets and operations
lineage report      # Generate compliance report
lineage clear       # Reset database
```

## Jupyter

```python
%load_ext autolineage
%lineage_start

# Your code here...

%lineage_summary
%lineage_show
```

## Contributing

Contributions welcome. Fork, branch, add tests, submit PR.

```bash
git clone https://github.com/kishanraj41/autolineage.git
cd autolineage
pip install -e .
pytest tests/ -v  # 34 tests passing
```

## Citation

```bibtex
@software{autolineage2025,
  author = {Vandhavasi Goutham Kumar, Kishan Raj},
  title = {AutoLineage: Automatic In-Memory Data Lineage Tracking for ML Pipelines},
  year = {2025},
  url = {https://github.com/kishanraj41/autolineage}
}
```

## License

MIT — see [LICENSE](LICENSE).
