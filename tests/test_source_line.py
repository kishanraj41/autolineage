"""Caller file and line are stored on every hooked record."""

import inspect
import os

import pandas as pd

from autolineage.core.analyzer import LineageAnalyzer
from autolineage.core.tracker import UnifiedTracker
from autolineage.core import TransformationRecord
from autolineage.hooks.registry import HookRegistry


def test_dropna_records_the_caller_line():
    tracker = UnifiedTracker()
    registry = HookRegistry()
    registry.install_all(tracker)
    try:
        frame = pd.DataFrame({"a": [1.0, None, 3.0]})
        marked = inspect.currentframe().f_lineno + 1
        frame.dropna()
    finally:
        registry.uninstall_all()
    recs = [rec for rec in tracker.records if rec.operation == "dropna"]
    assert recs
    assert recs[0].metadata["source_line"] == marked
    assert recs[0].metadata["source_file"] == os.path.abspath(__file__)


def test_source_stamp_opt_out(monkeypatch):
    monkeypatch.setenv("AUTOLINEAGE_SOURCE_STAMP", "0")
    tracker = UnifiedTracker()
    registry = HookRegistry()
    registry.install_all(tracker)
    try:
        pd.DataFrame({"a": [1.0, None]}).dropna()
    finally:
        registry.uninstall_all()
    recs = [rec for rec in tracker.records if rec.operation == "dropna"]
    assert recs
    assert "source_file" not in recs[0].metadata
    assert "source_line" not in recs[0].metadata


def test_library_frame_uses_the_filename(tmp_path):
    from autolineage.hooks import _is_library_frame
    user_module = tmp_path / "pandas_utils.py"
    user_module.write_text("x = 1\n", encoding="utf-8")
    assert _is_library_frame(str(user_module)) is False
    assert _is_library_frame(pd.__file__) is True


def test_ranked_causes_names_the_largest_drop_line():
    tracker = UnifiedTracker()
    tracker.record(TransformationRecord(
        operation="filter", rows_before=100, rows_after=10,
        metadata={"source_file": "pipe.py", "source_line": 4},
    ))
    tracker.record(TransformationRecord(
        operation="train_test_split", rows_before=10, rows_after=7,
        metadata={"source_file": "pipe.py", "source_line": 9},
    ))
    analyzer = LineageAnalyzer(tracker)
    ranked = analyzer.ranked_causes()
    cause = analyzer.localize_root_cause()
    assert ranked[0]["source_line"] == 4
    assert ranked[0]["operation"] == "filter"
    assert cause.root_step_index == ranked[0]["step_index"]
