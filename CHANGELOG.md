# Changelog

All notable changes to AutoLineage will be documented in this file.

## Unreleased

### Added
- `CountVectorizer` and `TfidfVectorizer` `fit`, `transform`, and `fit_transform` are recorded, as is construction of either class. A `TfidfVectorizer` call does not also record the `CountVectorizer` method it invokes, and `fit` does not also record the `fit_transform` it invokes. The held-out set was not used.
- Estimator and preprocessor construction is recorded. Calling `OneHotEncoder(handle_unknown="ignore")`, `Pipeline(...)`, `GridSearchCV(...)` or any other hooked scikit-learn class from user code adds one `configure` record (`<Class>.__init__`) with `get_params(deep=False)` and the caller's line. Constructions made inside scikit-learn (`clone` in a search, the trees of a forest) are not recorded, and classes without their own `__init__` (LabelEncoder) are left alone. On the three development scripts that run offline, pipeline-line coverage went from 26/54 to 40/54 (Telco 32/33, email sorting 5/9, `RF.py` 3/12). Those 14 lines are configuration records, not data operations. The held-out set was not used to choose or measure this change, and the published held-out coverage is unchanged. A fingerprint saved before this change reports each constructor as a new operation at info severity; re-record the baseline to compare configuration.

### Documentation
- `docs/api.md`: API reference for the public surface (`autolineage.auto`, `UnifiedTracker`, `TransformationRecord`, `LineageAnalyzer` and its thresholds, visualisation, OpenTelemetry, hook providers).
- Docstrings on every public tracker, analyzer and registry method that lacked one.
- `paper.md` restructured to the current JOSS sections (state of the field, software design, research impact statement, AI usage disclosure); mlinspect, Vamsa and noWorkflow cited.
- README: localization described as a ranked heuristic, per-call overhead stated as machine-dependent, related research tools named, project history noted.

## v0.7.1 (2026-10-15)

### Fixed
- Derived pandas frames no longer keep the parent's lineage id. pandas copies `attrs` onto the result, so `get_or_assign` was returning the parent's id and the graph collapsed to one node. A result that is a new object now gets `assign_id`, which replaces that copied id. In-place calls and `__setitem__` read the parent id before the call and assign a fresh one after it. `assign_id` still fires the RudriQ callback.
- An inserted filter is blamed even when the baseline already contains a filter. Operation sequences are aligned with `difflib.SequenceMatcher`, and an unmatched current step that removed rows is treated as inserted. Occurrence keys are no longer compared to the wrong partner after an insert.
- `__setitem__` and `Series.map` decide "called from the library" by the caller's filename, the same rule as source stamping. A user module named `pandas_utils` is no longer skipped. `Series.map` records the mapped series, not a throwaway `to_frame()` copy.

### Changed
- Duration anomalies ignore baselines under 50 ms. The previous floor was 1 ms, which treated timer noise as a pipeline change.
- `AUTOLINEAGE_SOURCE_STAMP=0` turns off caller file and line on records, and turns off storing the caller's source text on a filter. The default remains on.

## v0.7.0 (2026-10-10)

Highlights: OpenTelemetry export (`autolineage[otel]`); column-set membership in the analyzer; early-bound imports in scripts and notebooks are now rebound and tracked instead of silently missed. The synthetic planted-bug script is a regression test under `tests/regression/planted_bugs/` and is not a reported result. Upgrade note: fingerprints saved by 0.6.x still load, but `concat:N` keys may shift (see Changed), so re-record any baseline you compare against.

### Added
- Project logo and brand assets in `docs/brand/` (mark, lockups, icons, favicon, social preview), shown in the README header.
- OpenTelemetry export behind a new `otel` extra (`pip install autolineage[otel]`). `autolineage.otel.enable_otel_export(tracker=None, tracer_provider=None)` turns every recorded operation into a span named `<library>.<operation>` under one `autolineage.run` span, timed by the operation's measured duration, with `autolineage.*` attributes: lineage IDs (`child_id`, `parent_ids`), rows before/after and delta, input/output shape, columns added/removed (capped at 50 names plus a count), duration, content hash, metric name and value. Uses the caller's tracer provider; configures no exporter. Only operations recorded after the call are exported; `shutdown()` stops export and ends the run span. Built on the existing post-record callback; no change to tracking when not enabled.
- `UnifiedTracker.unregister_post_record_callback(callback)`.
- `tests/test_otel.py`: 8 tests (span per operation under one run span, lineage/shape/metric attributes, shutdown idempotent and final, pre-enable operations not exported, attribute capping and OTel-valid types, callback unregister). Skipped when the extra is not installed.
- Early-bound imports are rebound instead of only warned about. A hooked module-level function imported into `__main__` before the hooks were installed (`from sklearn.metrics import f1_score`, `from sklearn.model_selection import train_test_split`, `from pandas import merge`, `get_dummies`, `read_csv`, ...) is rebound to the tracked version after installation, so those calls are recorded; one warning lists every name rebound. `uninstall_all()` restores the original binding unless the user reassigned the name in the meantime. Set `AUTOLINEAGE_REBIND_EARLY_IMPORTS=0` to keep the previous warn-only behaviour. Previously the warning covered sklearn metrics only and the calls went unrecorded; worse, the untracked call's internal pandas/sklearn operations (`filter`, `concat`, `LabelEncoder.fit`) were recorded as if the user had made them. Scope: `__main__` only (scripts and notebooks); names bound early inside other modules are not touched.
- `tests/test_early_binding.py`: 12 tests (metrics, aliased imports, `train_test_split`, pandas module functions, single warning, uninstall restore, user reassignment preserved, reinstall, opt-out, unrelated and private names untouched).
- `tests/regression/planted_bugs/`: the synthetic pipeline, kept as a regression test that each case still names the operation the bug was written into. It is not a benchmark result.
- `benchmarks/real/`: the held-out evaluation. The protocol, manifest, and search logs are the selection record. The held-out set was scored once on the evaluated build (`benchmarks/real/heldout_results/evaluated_build/`) and re-scored after the v0.7.1 lineage-ID fix (the JSON files directly in `benchmarks/real/heldout_results/`). The paper quotes the re-score. Development rates are not published.
- `pd.get_dummies` is now a hooked operation (`operation="get_dummies"`, pandas hook count 64 -> 65, total 288 -> 289). The record carries the encoded columns, the dummy columns created, and the `columns`/`prefix`/`drop_first`/`dummy_na`/`dtype` parameters. Internal pandas calls made by `get_dummies` (`concat`, `__getitem__`, `drop`) are swallowed by the reentrancy guard rather than recorded as separate operations.
- Column-set membership in the analyzer. `RunFingerprint` gains `output_columns`, `columns_added`, `columns_removed` (per `op:occurrence` key) and `columns_seen` (whole run). `detect_anomalies()` emits three new anomaly metrics, each attributed to a single operation: `columns_introduced` (columns the baseline never saw), `columns_retained` (columns the baseline deliberately removed that this run never removes — the target-leakage signature, always critical), and `columns_missing` (columns the baseline created that this run never creates). `localize_root_cause()` credits each of these 0.4 (`LineageAnalyzer.MEMBERSHIP_WEIGHT`) to the operation where the change originated, never to downstream operations that inherit it, and the explanation names the columns. Disable with `thresholds={'column_membership': False}`. Frames wider than `LineageAnalyzer.MAX_TRACKED_COLUMNS` (5000) are not stored. Fingerprints written by earlier versions load unchanged; the membership checks are a no-op against them.
- Every pandas transform record now populates `input_columns` / `output_columns` (previously always `None`).
- `tests/test_column_membership.py`: 18 tests covering the hook, fingerprint round-trip and backward compatibility, the encoding and leakage planted bugs localizing exactly, and the no-false-positive cases (inserted operation, identical runs, threshold off).

### Changed
- `pd.merge` and `pd.concat` hooks now honour the same reentrancy depth guard as the DataFrame method hooks. Previously a `concat` issued internally by another pandas call (e.g. inside `get_dummies`) was recorded as a top-level operation; it is not any more, so the `concat:N` keys of a fingerprint recorded with 0.6.3 may not line up with one recorded now for the same script.
- The synthetic pipeline's harness is fixed for pandas 3.0, where string columns are `str` dtype rather than `object` and the old `dtype == object` filter crashed `StandardScaler`.
- `docs/quickstart.md` rewritten for the current API.
- README, RELEASE_NOTES and the JOSS paper described the 84.7 µs overhead figure as coming from a 37-operation pipeline. It comes from `paper/microbenchmark_v2.py`, which times one hooked call (`df.dropna()` on a 50-row DataFrame); the description now says so. The figure itself is unchanged.
- Release workflow: runs in a `pypi` environment for PyPI trusted publishing, refuses to publish when the tag, `pyproject.toml` and `__version__` disagree, and runs `twine check --strict` before upload.

### Removed
- The four placeholder hook providers `numpy_hooks.py`, `xgboost_hooks.py`, `lightgbm_hooks.py` and `polars_hooks.py`. Each was 11 lines, installed 0 hooks, and was registered in `_PROVIDERS` anyway. No behaviour change; real Polars support is planned for v0.8.0.
- Stale documentation and examples left over from the v0.1 to v0.3 architecture: `docs/cli.md` and `docs/compliance.md` (described a `lineage` CLI and a compliance reporter removed in v0.4.1), and eleven example scripts plus `examples/jupyter_demo.ipynb` that imported `DatasetTracker`, `autolineage.database`, `autolineage.tracker` or `%lineage_start` and failed on import against any release since 0.4.1. Remaining examples (`anomaly_demo.py`, `pipeline.py`, `quickstart.ipynb`) all run against the current release.

## v0.6.3 (2026-09-29)

### Fixed
- Package metadata: the wheel now reports `__version__ == "0.6.3"` (the 0.6.2 wheel on PyPI reported 0.6.1) and the author is listed as Kishan Raj VG, matching the SSRN preprint and the citation block.
- README images and links are absolute URLs so the PyPI project page renders the demo GIFs and the license link.

### Added
- README hero: PyPI, Python, CI, license, SSRN and Colab badges; `docs/screenshots/autolineage-hero.gif`, a recording of `examples/anomaly_demo.py` catching an F1 collapse and naming the filter that caused it; `docs/screenshots/autolineage-quickstart.gif`, install to interactive graph in 30 seconds.
- `examples/quickstart.ipynb`: a Colab notebook that installs the package, tracks a pipeline, plants a one-line bug and shows the analyzer localizing it. Badge in the README opens it directly.
- `examples/pipeline.py`: the 22-line script from the quickstart recording.
- `docs/hero.tape`, `docs/quickstart.tape`, `docs/quickstart_browser.py`: the recordings are reproducible.
- JOSS paper draft (`paper.md`, `paper.bib`), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and the synthetic pipeline now at `tests/regression/planted_bugs` (shipped on `main` in July, first included in a release here).

### Notes
- No changes to the `autolineage` package code since v0.6.2. Safe to upgrade.

## v0.6.2 (2026-06-13)

### Fixed
- Version strings in `pyproject.toml` and `autolineage/__init__.py` synced to 0.6.2. The 0.6.2 wheel was uploaded before this commit, so it reports `__version__ == "0.6.1"`; corrected in v0.6.3.

## v0.6.1 (2026-05-05)

### Fixed
- `UnifiedTracker.get_or_assign(obj)` now fires `register_assign_id_callback` even when an existing lid is returned (previously only `assign_id` itself fired the callback). This matters for the common pandas pattern where attrs get preserved across operations: `read_csv` produces a DataFrame with an attrs dict; `sort_values` returns a NEW DataFrame instance whose attrs were copied (carrying the existing `_lineage_id`); `_get_or_assign` for that new instance returned the existing lid without firing callbacks. Downstream consumers (RudriQ) ended up with `id(first_df) -> lid` registered but `id(sort_values_result) -> lid` missing, breaking identity-based correlation in chains longer than two operations.
- 2 new regression tests in `tests/test_callbacks.py::TestGetOrAssignFiresCallbackOnReuse`.

### Notes
- Backward-compatible. Code that registered a callback expecting "fire-once-per-lid" semantics will now fire on every reuse. Callbacks should be idempotent (RudriQ's was). If a consumer needs fire-once semantics, dedupe by `(id(obj), lid)` inside the callback.

## v0.6.0 (2026-05-05)

### Added
- `UnifiedTracker.register_post_record_callback(callback)`: register a callback that fires after each `record()` call with the `TransformationRecord` that was just appended to `self.records`. By the time the callback fires, `tracker.records[-1]` is the same record and `tracker.nodes[record.child_id]` is queryable for shape/columns/content_hash. Distinct from `register_assign_id_callback` (which fires per-object-assignment and is the right hook for object-identity registration); this hook is the right one for operation-level mirroring (carries `parent_ids`, `library`, `operation`, `duration_ms`, etc.).
- `tests/test_callbacks.py::TestRegisterPostRecordCallback`: 6 tests covering the new API (fires with record, record-already-stored invariant, registration-order multiple, exception caught, one buggy doesn't block others, zero-callback no-op).

### Notes
- Additive non-breaking change. Existing callers are unaffected. MINOR version bump per semver.
- Used by RudriQ v0.0.6+ to mirror records as canonical TraceNodes/TraceEdges in its DuckDB so audit reports show full data→LLM ancestry without 'external' placeholders.

## v0.5.0 (2026-05-04)

### Added
- `UnifiedTracker.register_assign_id_callback(callback)`: register a callback that fires after each `assign_id` call with `(obj, lid)`. This is the only hook point where both the live Python object reference and its lineage ID are available together — `TransformationRecord` only carries lineage IDs (strings), not the underlying objects. Used by downstream consumers (e.g. RudriQ) to mirror `id(obj) -> lid` mappings into their own registries for cross-domain linking. Callbacks run in the calling thread; exceptions are caught and logged at DEBUG, never propagated. Multiple callbacks fire in registration order; one buggy callback does not block others.
- `tests/test_callbacks.py`: 6 tests covering the new callback API (single fire, multiple callbacks fire in order, exception caught, one buggy doesn't block others, zero-callback no-op, callback observes `obj -> lid` mapping already stored at fire time).

### Notes
- Additive non-breaking change. Existing code that does not call `register_assign_id_callback` is unaffected. MINOR version bump per semver.

## v0.4.1 (2026-04-26)

### Removed
- Legacy modules from the v0.1.0 architecture that were no longer used and never reached production: `cli.py`, `database.py`, `df_tracker.py`, `graph.py`, `magic.py`, `reporter.py`, `tracker.py`, `transform_hooks.py`, `auto_legacy.py`, `hooks.py`. These shipped accidentally in the v0.4.0 wheel.

### Changed
- `scikit-learn` and `pyspark` are now declared as optional dependency extras (`pip install autolineage[sklearn,pyspark]`) instead of being required transitively. The base install pulls only `pandas` and `numpy`.
- Removed unused required dependencies: `networkx`, `matplotlib`, `click`.
- License declaration migrated to SPDX expression format (resolves setuptools deprecation warning).

### Fixed
- v0.4.0 wheel installed legacy modules that were never accessible from the public API but added 12 dead files to user installations.

## v0.4.0 (2026-04-26)
[... existing v0.4.0 content ...]

## [0.1.0] - 2025-01-29

### Added
- Automatic data lineage tracking for pandas, numpy, pickle, joblib
- Visual lineage graphs (PNG and interactive HTML)
- CLI interface (`lineage` command)
- EU AI Act Article 10 compliance report generation
- Jupyter notebook magic commands
- SQLite-based lineage storage with SHA-256 hashing
- Comprehensive documentation and examples

### Features
- Zero manual logging required
- Automatic function hooking for popular ML libraries
- Cryptographic file verification
- Complete audit trail
- Reproducibility documentation

## [Unreleased]

### Planned
- MLflow integration
- Git integration for code versioning
- Column-level lineage tracking
- Data drift detection
- Team collaboration features
- Cloud storage support (S3, GCS, Azure Blob)