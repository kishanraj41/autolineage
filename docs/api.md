# API reference

Public API of AutoLineage 0.7.x. Everything here is importable from `autolineage`, `autolineage.auto` or `autolineage.otel`. Anything else (names starting with `_`, provider internals under `autolineage.hooks.*`, `hooks_legacy`) may change between releases without notice.

Docstrings are the source of truth, for example `help(autolineage.LineageAnalyzer.detect_anomalies)`.

## Turning tracking on and off: `autolineage.auto`

| Call | What it does |
|---|---|
| `import autolineage.auto` | Installs hooks for every installed framework (pandas, scikit-learn, PySpark) and starts a global tracker. Put it before your other imports. A `multiprocessing` or `multiprocess` child started afterwards is recorded into that tracker when the child is joined. |
| `start_tracking() -> UnifiedTracker` | The same thing, called explicitly. Safe to call repeatedly; returns the global tracker. |
| `stop_tracking() -> None` | Removes the hooks and discards the global tracker. |
| `get_tracker() -> UnifiedTracker \| None` | Returns the global tracker, or `None` when tracking is off. |
| `get_summary() -> dict \| None` | Returns `get_tracker().get_summary()`. |
| `visualize(output=None, *, inline=False, open_browser=True)` | Writes the interactive HTML view of the global tracker. |

Environment variable: setting `AUTOLINEAGE_SOURCE_STAMP=0` stops records from storing the file and line of the user code that made each call.

## `UnifiedTracker`

The tracker holds the graph: `nodes` (one per lineage ID) and `records` (one `TransformationRecord` per user-visible framework call).

Queries:

| Method | Returns |
|---|---|
| `get_summary()` | `total_records`, `total_nodes`, `by_library`, `total_rows_filtered`, `total_column_changes`, `libraries_tracked` |
| `get_full_graph()` | `{"nodes": ..., "edges": [record dicts], "file_mappings": {path: lineage_id}}` |
| `get_chain(lid)` | The records upstream of a lineage ID, oldest first |
| `get_timing_profile()` | Operations sorted by duration, slowest first |
| `get_id(obj)` | The lineage ID attached to a DataFrame or other object, or `None` |

Export methods: `visualize(output=None, *, inline=False, open_browser=True)`, `to_dot(*, rankdir="TB")` and `to_mermaid()`. In Jupyter, a tracker displays itself as HTML.

Extension points, for integrations and hook providers:

| Method | Use |
|---|---|
| `register_post_record_callback(cb)` / `unregister_post_record_callback(cb)` | `cb(record)` runs after every record |
| `register_assign_id_callback(cb)` | `cb(obj, lid)` runs whenever an object gets a lineage ID or keeps its existing one |
| `assign_id(obj, *, source="unknown", filepath=None)`, `get_or_assign(obj, **kw)` | Attach lineage IDs (hook providers call these) |
| `record(rec)` | Add a record (hook providers call this) |

## `TransformationRecord`

A dataclass with one instance per operation.

- **Fields:** `id`, `library`, `category`, `operation`, `parent_ids`, `child_id`, `parameters`, `input_shape`, `output_shape`, `input_columns`, `output_columns`, `columns_added`, `columns_removed`, `rows_before`, `rows_after`, `duration_ms`, `content_hash`, `metadata`, `timestamp`. When source stamping is on, `metadata` contains `source_file` and `source_line`.
- **Categories:** `io`, `transform`, `preprocess`, `split`, `train`, `predict`, `evaluate`, `action` (PySpark), and `configure` (an estimator or preprocessor constructed in user code; `parameters` holds `get_params(deep=False)`).
- **Properties:** `row_delta`, `col_delta`.
- **Method:** `to_dict()`.

## `LineageAnalyzer(tracker, thresholds=None)`

Compares a run against a baseline and names the operation most likely to have changed a metric.

| Method | What it does |
|---|---|
| `fingerprint() -> RunFingerprint` | Summarises the current run |
| `save_fingerprint(path, append=True)` | Writes the fingerprint to JSON, keeping a history of up to 50 runs |
| `load_baseline(path) -> bool` / `set_baseline(fp)` | Sets the run to compare against |
| `detect_anomalies(baseline=None) -> list[Anomaly]` | Returns deviations, most severe first. Without a baseline, only within-run checks are applied. |
| `localize_root_cause(metric_name=None, baseline=None) -> RootCause \| None` | Names one operation. The default metric is the one with the largest relative drop. |
| `ranked_causes(metric_name=None, baseline=None) -> list[dict]` | Every scored operation, best first. Entries include `source_line` when one was recorded. |

`thresholds` overrides any of the keys in `LineageAnalyzer.DEFAULT_THRESHOLDS`:

| Key | Default | Meaning |
|---|---|---|
| `row_delta_pct` | 20.0 | Deviation in row-change rate that raises an anomaly |
| `col_count_change` | 0 | Allowed change in column count |
| `new_operation` / `missing_operation` | True | Report operations added to or missing from the sequence |
| `metric_drop_pct` | 5.0 | Relative metric drop counted as a regression |
| `duration_spike_pct` | 200.0 | Duration increase that is reported. Operations under 50 ms in the baseline are ignored. |
| `column_membership` | True | Compare column names, not only column counts |

The defaults are heuristics. They have not been tuned on the held-out benchmark (see `benchmarks/real/PROTOCOL.md`).

Result types, each with `to_dict()`:

- **`Anomaly`:** `severity` (`info` / `warning` / `critical`), `operation`, `step_index`, `metric`, `expected`, `actual`, `deviation`, `message`.
- **`RootCause`:** `metric_name`, `metric_baseline`, `metric_actual`, `root_operation`, `root_step_index`, `impact_score`, `explanation`, `evidence`.
- **`RunFingerprint`:** also has `from_dict()`.

## Visualisation: `autolineage.visualize`, `to_dot`, `to_mermaid`

Module-level equivalents of the tracker methods. Each takes the tracker as its first argument.

## OpenTelemetry: `autolineage.otel` (`pip install "autolineage[otel]"`)

`enable_otel_export(tracker=None, tracer_provider=None, *, run_name="autolineage.run") -> OTelExporter` exports every record as a span, with the lineage IDs as span attributes. `record_attributes(rec)` returns the attribute dictionary for a single record.

## Adding a framework: `BaseHookProvider` and `HookRegistry`

To support a new framework, subclass `BaseHookProvider` and implement:

- `name`
- `required_package`
- `install(tracker) -> int`, which returns the number of methods hooked
- `uninstall()`

Then register the provider in `autolineage/hooks/registry.py`. `HookRegistry.install_all(tracker)` and `uninstall_all()` install and remove every available provider. The steps are in `CONTRIBUTING.md`, and `autolineage/hooks/pandas_io.py` is the smallest working example.
