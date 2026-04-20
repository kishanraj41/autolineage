# Competitive Comparison: AutoLineage vs ML Observability Tools
## For Paper Section 6 (Related Work) — Table 2

### Key Claim
No existing tool provides **zero-code, operation-level, end-to-end lineage**
across **multiple ML frameworks** in a single unified DAG.

### Table 2 (verbatim for paper)

| Tool | Year | Zero-Code | Operation-Level | Cross-Framework | E2E Trace | Anomaly Det. | License |
|------|------|-----------|----------------|-----------------|-----------|--------------|---------|
| AutoLineage | 2025 | Yes | Yes | Yes (3) | Yes | Yes | MIT |
| MLflow | 2018 | No (requires `mlflow.log`) | No | No | No | No | Apache 2.0 |
| Evidently | 2020 | No (requires `Report()`) | No | No | No | Drift only | Apache 2.0 |
| Arize Phoenix | 2021 | No (requires SDK) | No | LLM only | No | LLM only | ELv2 |
| WhyLabs/whylogs | 2021 | No (requires `whylogs.log`) | No | No | No | Drift only | Apache 2.0 |
| Langsmith | 2023 | No (requires `@traceable`) | No | LLM only | No | No | Proprietary |
| Great Expectations | 2018 | No (requires expectations) | No | No | No | Schema-based | Apache 2.0 |
| DVC | 2018 | No (requires `dvc.yaml`) | No | No | No | No | Apache 2.0 |
| OpenLineage | 2021 | No (requires integration) | Job-level | Spark only | No | No | Apache 2.0 |
| DataLineagePy | 2024 | No (requires wrapper class) | Yes | pandas only | No | No | MIT |
| Spline | 2019 | Yes (Spark-only) | Plan-level | Spark only | No | No | Apache 2.0 |

### Row-by-Row Source Citations (for Related Work prose)

| Tool | Source | Key Quote (paraphrased) |
|------|--------|-------------------------|
| MLflow | Zaharia et al. 2018 | Experiment tracking via explicit log_param/log_metric calls |
| Evidently | ProductOwl review Jan 2026 | "has no built-in capability to track data provenance, history, or flow" |
| Arize Phoenix | arize.com docs | Tracing focused on LLM applications |
| WhyLabs | whylabs.ai/whylogs README | Statistical profiling; user inserts .log() calls |
| Langsmith | docs.smith.langchain.com | `@traceable` decorator required per function |
| OpenLineage | openlineage.io | Designed for job-level (Airflow, Spark) |
| DataLineagePy | pypi.org/project/datalineagepy | Requires LineageDataFrame wrapper class |
| Spline | absaoss.github.io/spline | Automatic but Spark-only, execution-plan level |

### The Unique Position Narrative (for paper)

Four dimensions define "complete" lineage coverage for ML pipelines:

1. **Zero-code**: activation via import, no decorators or config
2. **Operation-level**: individual DataFrame operations, not job boundaries
3. **Cross-framework**: same interface for pandas, sklearn, Spark
4. **End-to-end trace**: raw data -> transformations -> model -> metrics in one DAG

Only AutoLineage satisfies all four. Specifically:
- MLflow/WandB/Evidently/Arize: not zero-code (explicit log calls or configs)
- OpenLineage/Spline: job- or plan-level, not operation-level
- DataLineagePy: requires wrapping DataFrames in a custom class
- All other tools: single-framework or single-stage (data-only or model-only)

### Market Context for Introduction

- Data governance market: USD 3.91B in 2026, projected USD 9.62B by 2030 (OvalEdge 2026)
- EU AI Act effective Aug 2024, requires lineage documentation for high-risk AI
- Fines up to EUR 35M or 7% global turnover
- 92% of AI practitioners experience "data cascades" (Sambasivan et al. 2021, n=53)
- 68% of data teams migrating away from code-heavy pipelines (Skyvia 2026 survey, n=200)

### Honest Limitations (for Discussion)

- AutoLineage works within a **single Python process**. Distributed pipelines
  spanning multiple machines require manual trace correlation (future work:
  OpenTelemetry export).
- Monkey-patching is **version-sensitive**: library updates may require hook
  updates. AutoLineage v0.3 is tested against pandas 2.x, scikit-learn 1.x,
  and PySpark 3.x/4.x.
- **Python-only**. R, Julia, Java ML workflows are out of scope.
