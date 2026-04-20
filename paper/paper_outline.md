# AutoLineage Paper - Complete Outline

## Title
"AutoLineage: Zero-Code End-to-End Data Lineage for Machine Learning Pipelines"

## Authors
- Kishan Raj Vandhavasi (corresponding author)
- Goutham Kumar (co-author pending consent)

## Target Venue
arXiv (cs.SE + cs.LG) as first submission.
Follow-up: JOSS (Journal of Open Source Software) or NeurIPS workshop on MLOps/Reproducibility.

---

## Section 1: Introduction (1.5 pages)

### Hook
ML systems fail silently. 92% of practitioners experience "data cascades"
(Sambasivan et al. 2021). When accuracy drops from 0.95 to 0.60 overnight,
was it a model change, a new feature, or a silent upstream data bug? Without
automatic provenance, the investigation starts with `git blame` and ends with
print statements.

### The Gap
ML observability tools monitor models (MLflow, W&B) or LLMs (Langsmith, Arize
Phoenix), but the pipeline between raw data and model input is a black box.
Data versioning tools (DVC) track files, not in-memory operations.
Data-quality tools (Great Expectations) validate values but not lineage.

### Our Contribution
AutoLineage — a plugin-based, zero-code lineage tracker that records every
DataFrame operation, model training step, and metric evaluation across
pandas, scikit-learn, and PySpark in a single unified DAG. One line activates
it:
```python
import autolineage.auto
```

### Four Contributions
1. A **plugin architecture** (BaseHookProvider) extensible to any Python ML library
2. **288 hooks** across pandas, scikit-learn, and PySpark with <10% overhead
3. **End-to-end trace** connecting raw data through metrics in one DAG
4. **Lineage-based anomaly detection and root-cause localization** (novel)

### Paper Map
Section 2: background and motivation.
Section 3: system architecture.
Section 4: implementation.
Section 5: evaluation on 3 pipelines, a case study, and benchmarks.
Section 6: related work.
Section 7: limitations and future work.
Section 8: conclusion.

---

## Section 2: Background and Motivation (1 page)

### 2.1 The ML lineage gap
ML pipelines: data -> transformations -> features -> model -> predictions.
Current tools:
- Track endpoints (data catalogs, model registries)
- Require explicit instrumentation (mlflow.log, whylogs.log)
- Cover a single stage (data OR model OR LLM)

None provide automatic, operation-level trace from read_csv to f1_score.

### 2.2 Limitations of existing approaches
- **Manual logging (MLflow, W&B):** developers forget; coverage incomplete
- **Data validation (Great Expectations):** detects bad output, doesn't trace cause
- **Model monitoring (Evidently, Arize):** post-deployment, no training trace
- **Data versioning (DVC):** file-level, not operation-level
- **Enterprise lineage (OpenLineage, Atlan):** SQL/job-level, not DataFrame-level

### 2.3 Design requirements
- R1: **Zero code changes** — no decorators, no config
- R2: **Operation-level granularity** — every dropna, merge, fit, predict
- R3: **Cross-framework** — pandas, sklearn, PySpark, extensible
- R4: **Low overhead** — <10% pipeline time
- R5: **End-to-end trace** — unified DAG from data through metrics
- R6: **Actionable insights** — not just recording, but anomaly detection and
  root-cause analysis

---

## Section 3: System Architecture (2 pages)

### 3.1 Overview
[Figure 1: Architecture diagram — 4 layers]
- Layer 1: user code (unchanged)
- Layer 2: hook providers (plugins per library)
- Layer 3: unified core (tracker, record type, analyzer)
- Layer 4: outputs (trace, DAG, anomalies, root causes)

### 3.2 Plugin architecture (BaseHookProvider)
Each library = one Python file implementing `install(tracker) -> int` and
`uninstall() -> None`. HookRegistry auto-discovers; missing libraries
silently skipped. Adding a new library is ~200 lines.

### 3.3 Hook mechanism
- Import-time monkey-patching
- Post-execution recording (original runs first, metadata captured after)
- **Depth-counter reentrancy guard** prevents recording internal library calls
  (e.g., RandomForest's 100 inner DecisionTree predictions)
- `df.attrs` for pandas lineage IDs; WeakValueDictionary for sklearn/PySpark

### 3.4 TransformationRecord (unified schema)
Fields: `library, category, operation, parent_ids, child_id, input_shape,
output_shape, columns_added, columns_removed, rows_before, rows_after,
duration_ms, content_hash, metadata`

Categories: `io, transform, split, preprocess, train, predict, evaluate, action`

### 3.5 UnifiedTracker
Single in-memory DAG across libraries. Query API:
- `get_chain(lid)` — ancestor chain
- `get_summary()` — aggregate stats
- `get_timing_profile()` — slowest operations
- `get_full_graph()` — serializable DAG

### 3.6 LineageAnalyzer (novel research contribution)
- `fingerprint()` — compact run signature (operation sequence, row deltas,
  column counts, metrics)
- `detect_anomalies(baseline)` — flag deviations in row drops, column
  changes, metric degradations, duration spikes
- `localize_root_cause(metric)` — walk DAG backward, score each
  transformation by deviation from baseline, return highest-impact operation

---

## Section 4: Implementation (1.5 pages)

### 4.1 pandas provider (64 hooks)
- 10 I/O functions (5 read, 5 write)
- 54 transform methods (dropna, fillna, merge, groupby, etc.)
- Handling `*args/**kwargs` for path resolution in write methods
- `__getitem__` hook distinguishes select vs filter

### 4.2 sklearn provider (175 hooks)
- train_test_split with ratio/size capture
- 30+ estimator classes x {fit, predict, predict_proba, score}
- 18 preprocessor classes x {fit, transform, fit_transform}
- 15 metric functions
- **Depth-counter guard** prevents noise from internal library calls

### 4.3 PySpark provider (49 hooks)
- Handles PySpark 4.x class alias (`pyspark.sql.classic.dataframe`)
- Lazy transforms + eager actions distinguished
- groupBy tagging via `_autolineage_parent`

### 4.4 Extensibility
Table: hooks, lines of code, and effort per provider
- pandas I/O: 10 hooks, ~100 LoC, 1 hour
- pandas transforms: 54 hooks, ~280 LoC, 3 hours
- sklearn: 175 hooks, ~500 LoC, 4 hours
- PySpark: 49 hooks, ~450 LoC, 4 hours

Adding XGBoost or LightGBM would follow the sklearn pattern; ~200 LoC each.

---

## Section 5: Evaluation (2.5 pages)

### 5.1 Experimental setup
- Hardware: [Kishan to provide: CPU model, RAM, OS, Python version]
- pandas X.Y, scikit-learn X.Y, PySpark X.Y
- AutoLineage v0.3
- 5 repetitions, mean +- std reported

### 5.2 Pipeline 1: Credit Card Fraud Detection (pandas + sklearn)
- Dataset: 284,807 transactions, 31 columns, fraud rate 0.173%
- Operations tracked: [from output]
- Results:
  - RandomForest: Acc=0.9995, F1=0.83, AUC=0.987
  - LogisticRegression (baseline): Acc=0.974, F1=0.11
  - **Cross-library DAG**: pandas transforms feed into sklearn split, scaler,
    fit, predict, and metrics — all in one trace
- Table 3: operation-by-operation breakdown

### 5.3 Pipeline 2: PySpark Retail Analytics
- Dataset: 541,909 transactions (UCI Online Retail)
- Operations: read.csv, filter, dropna, withColumn, groupBy.agg, join, count
- Proves cross-framework — same architecture, different library
- Table 4: operation counts

### 5.4 Case study: debugging with lineage (N=2)
- **Planted bug**: filter removes 99.99% of fraud cases
- **Manual (P1)**: X minutes, Y steps, detection method = print(df.shape)
- **AutoLineage (P2)**: Z minutes, W steps, detection method =
  analyzer.localize_root_cause()
- Qualitative: trace output made row drop (284K -> ~30) immediately visible
- Honest limitation: N=2, illustrative not statistical

### 5.5 Overhead benchmark
- Standardized pipeline (50K rows, 37 operations)
- WITHOUT AutoLineage: 0.050s +- 0.005s
- WITH AutoLineage: 0.054s +- 0.007s
- Overhead: 6.1% (0.08ms per operation)
- Table 5: full benchmark numbers
- Compared to typical MLflow logging overhead (~5-15% reported in literature)

### 5.6 Anomaly detection validation
- Planted-bug pipeline triggers anomaly:
  - `critical: filter removed 99.9% of rows`
  - `critical: f1_score = 0.0 (model may not be learning)`
- Root cause localization impact score: 0.99 (filter operation)
- Demonstrates the analyzer catches what the raw trace makes visible

---

## Section 6: Related Work (1 page)

Follow comparison_2026.md. Key claims:
- MLflow, W&B, Neptune: experiment tracking via manual logging
- Evidently, WhyLabs: data monitoring, no transformation tracking
- Arize, Langsmith: LLM observability, not traditional ML
- DVC: file versioning, not in-memory operations
- OpenLineage: job-level, not operation-level
- DataLineagePy: wrapper-class approach, pandas-only
- Spline: Spark-only, execution-plan level

AutoLineage uniquely satisfies zero-code + operation-level + cross-framework +
end-to-end trace.

Table 2 from comparison_2026.md goes here.

---

## Section 7: Discussion (0.5 pages)

### 7.1 Limitations
- Single-process (distributed multi-machine pipelines not supported)
- Monkey-patching sensitive to library updates
- Memory overhead for long-running notebooks (all records in memory)
- Python-only

### 7.2 Threats to validity
- Overhead measured on one machine (single-developer environment)
- Case study N=2 — illustrative, not statistical
- 100% recall claim relies on test-based verification, not formal proof

---

## Section 8: Future Work (0.5 pages)
- **OpenTelemetry export**: multi-process distributed tracing (months 5-8)
- Additional frameworks: Polars, XGBoost, LightGBM, PyTorch
- Web dashboard for DAG visualization
- LLM safety integration (hallucination tracking)
- Formal user study (N=20+)
- EU AI Act compliance report generation

---

## Section 9: Conclusion (0.5 pages)
- AutoLineage fills a real gap: zero-code, operation-level, end-to-end ML
  lineage
- Plugin architecture extensible to any Python ML library
- Published on PyPI, MIT license, tested and production-ready for
  single-process workflows
- Novel contribution: lineage-based anomaly detection and root-cause
  localization
- Open-sourced with 36 automated tests; reproducible evaluation in paper repo

---

## Figures & Tables checklist

| # | Type | Section | Source | Status |
|---|------|---------|--------|--------|
| F1 | Architecture diagram (SVG) | 3.1 | figures/architecture.svg | READY |
| F2 | Example lineage DAG | 3.5 | Generated from Credit Card run | PENDING output |
| F3 | Overhead chart | 5.5 | benchmark_results_v2.json | READY |
| T1 | Hook counts per provider | 4.4 | Handwritten | READY |
| T2 | Competitor comparison | 6 | comparison_2026.md | READY |
| T3 | Credit Card operations | 5.2 | Credit Card run | PENDING output |
| T4 | PySpark operations | 5.3 | PySpark run | PENDING |
| T5 | Case study timing | 5.4 | Kishan + Goutham session | PENDING |
| T6 | Benchmark results | 5.5 | benchmark_results_v2.json | READY |
| T7 | Anomaly detection triggered | 5.6 | Planted-bug run | PENDING |

---

## What Kishan Needs to Send Me

Before I write the LaTeX:
1. Credit Card pipeline output (clean trace, v3-fixed)
2. PySpark pipeline output (skip for now, can add later)
3. Case study completed templates (both P1 and P2)
4. Machine specs: CPU model, RAM, OS, Python/pandas/sklearn versions
5. Confirmation Goutham consents to being an author

Once I have these, I write the paper in one pass (~2 days).
