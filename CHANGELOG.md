# Changelog

All notable changes to AutoLineage will be documented in this file.

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