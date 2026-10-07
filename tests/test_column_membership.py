"""Tests for the pd.get_dummies hook and column-set membership analysis.

Covers the two planted-bug categories that previously localized to a
neighbouring operation (benchmarks/planted_bugs/README.md, cases 3 and
4): a one-hot encoding of the wrong column, and a label column that was
never dropped. Both must now localize to the exact operation.
"""

import json

import pytest
import pandas as pd
import numpy as np

from autolineage.core import TransformationRecord
from autolineage.core.tracker import UnifiedTracker
from autolineage.core.analyzer import LineageAnalyzer, RunFingerprint
from autolineage.hooks.registry import HookRegistry


@pytest.fixture
def hooked():
    """A fresh tracker with all hooks installed; uninstalls afterwards."""
    HookRegistry._globally_installed.clear()
    tracker = UnifiedTracker()
    registry = HookRegistry()
    registry.install_all(tracker)
    yield tracker
    registry.uninstall_all()
    HookRegistry._globally_installed.clear()


def _metric(tracker, name, value):
    tracker.record(TransformationRecord(
        library="sklearn", category="evaluate", operation=name,
        metadata={'metric_name': name, 'metric_value': value}))


def _frame(n=50, n_ids=10):
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "amount": rng.exponential(10, n),
        "region": rng.choice(["north", "south", "east", "west"], n),
        "customer_id": (np.arange(n) % n_ids).astype(str),
        "y": (rng.random(n) > 0.5).astype(int),
    })


# ----------------------------------------------------------------------
# The hook itself
# ----------------------------------------------------------------------

class TestGetDummiesHook:
    def test_records_one_operation_with_column_diff(self, hooked):
        df = _frame()
        out = pd.get_dummies(df, columns=["region"], drop_first=True, dtype=float)

        recs = [r for r in hooked.records if r.operation == "get_dummies"]
        assert len(recs) == 1
        rec = recs[0]
        assert rec.library == "pandas-transforms"
        assert rec.category == "transform"
        assert rec.columns_removed == ["region"]
        assert sorted(rec.columns_added) == sorted(c for c in out.columns if c.startswith("region_"))
        assert rec.input_shape == df.shape
        assert rec.output_shape == out.shape
        assert rec.input_columns == list(df.columns)
        assert rec.output_columns == list(out.columns)
        assert rec.parameters["columns"] == ["region"]
        assert rec.parameters["drop_first"] is True
        assert rec.parameters["n_dummy_columns"] == 3

    def test_internal_pandas_calls_are_not_recorded_separately(self, hooked):
        # get_dummies calls concat (and other hooked methods) internally.
        # Those must be swallowed by the reentrancy guard, not recorded
        # as top-level operations alongside the get_dummies record.
        df = _frame()
        pd.get_dummies(df, columns=["region"])
        ops = [r.operation for r in hooked.records]
        assert ops == ["get_dummies"]

    def test_lineage_links_parent_to_child(self, hooked):
        df = _frame()
        out = pd.get_dummies(df, columns=["region"])
        rec = hooked.records[-1]
        assert rec.parent_ids == [hooked.get_id(df)]
        assert rec.child_id == hooked.get_id(out)

    def test_series_input(self, hooked):
        s = pd.Series(["a", "b", "a"], name="letter")
        out = pd.get_dummies(s)
        rec = hooked.records[-1]
        assert rec.operation == "get_dummies"
        assert rec.input_columns == ["letter"]
        assert rec.output_columns == [str(c) for c in out.columns]

    def test_uninstall_restores_original(self):
        HookRegistry._globally_installed.clear()
        original = pd.get_dummies
        registry = HookRegistry()
        registry.install_all(UnifiedTracker())
        assert pd.get_dummies is not original
        registry.uninstall_all()
        HookRegistry._globally_installed.clear()
        assert pd.get_dummies is original


# ----------------------------------------------------------------------
# Fingerprint fields
# ----------------------------------------------------------------------

class TestFingerprintColumnSets:
    def test_fingerprint_carries_column_sets(self, hooked):
        df = _frame()
        pd.get_dummies(df, columns=["region"])
        fp = LineageAnalyzer(hooked).fingerprint()
        assert "get_dummies:1" in fp.output_columns
        assert fp.columns_removed["get_dummies:1"] == ["region"]
        assert len(fp.columns_added["get_dummies:1"]) == 4
        assert "region" in fp.columns_seen          # seen in the input
        assert "region_north" in fp.columns_seen    # seen in the output
        assert fp.has_column_sets()

    def test_round_trip_through_json(self, hooked, tmp_path):
        df = _frame()
        pd.get_dummies(df, columns=["region"])
        an = LineageAnalyzer(hooked)
        path = str(tmp_path / "fp.json")
        an.save_fingerprint(path)
        loaded = LineageAnalyzer(hooked)
        assert loaded.load_baseline(path)
        assert loaded._baseline.output_columns == an.fingerprint().output_columns
        assert loaded._baseline.columns_seen == an.fingerprint().columns_seen

    def test_old_fingerprint_without_column_sets_still_loads(self, hooked, tmp_path):
        df = _frame()
        pd.get_dummies(df, columns=["region"])
        old = {k: v for k, v in LineageAnalyzer(hooked).fingerprint().to_dict().items()
               if k not in ("output_columns", "columns_added", "columns_removed", "columns_seen")}
        path = tmp_path / "old.json"
        path.write_text(json.dumps([old]))
        an = LineageAnalyzer(hooked)
        assert an.load_baseline(str(path))
        assert not an._baseline.has_column_sets()
        # Membership checks are a no-op against an old baseline.
        metrics = {a.metric for a in an.detect_anomalies()}
        assert not metrics & {"columns_introduced", "columns_retained", "columns_missing"}

    def test_wide_frames_are_not_stored(self, hooked):
        wide = pd.DataFrame(np.zeros((2, LineageAnalyzer.MAX_TRACKED_COLUMNS + 1)))
        wide.dropna()
        fp = LineageAnalyzer(hooked).fingerprint()
        assert "dropna:1" not in fp.output_columns


# ----------------------------------------------------------------------
# Detection and localization on the two previously-proximate bug types
# ----------------------------------------------------------------------

def _run_encoding(tracker, buggy):
    df = _frame()
    df = pd.get_dummies(df, columns=["customer_id" if buggy else "region"], drop_first=True, dtype=float)
    df = df.drop(columns=[c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])])
    _metric(tracker, "f1_score", 0.6 if buggy else 0.9)


def _run_leakage(tracker, buggy):
    df = _frame()
    base = df if buggy else df.drop(columns=["y"])
    X = pd.get_dummies(base, columns=["region"], drop_first=True, dtype=float)
    X = X.drop(columns=[c for c in X.columns if not pd.api.types.is_numeric_dtype(X[c])])
    _metric(tracker, "f1_score", 1.0 if buggy else 0.9)


def _baseline_then_buggy(run):
    """Run the healthy pipeline on one tracker, the buggy one on another,
    and return an analyzer for the buggy run with the healthy baseline."""
    HookRegistry._globally_installed.clear()
    t_base = UnifiedTracker()
    r = HookRegistry()
    r.install_all(t_base)
    try:
        run(t_base, buggy=False)
    finally:
        r.uninstall_all()
        HookRegistry._globally_installed.clear()
    baseline = LineageAnalyzer(t_base).fingerprint()

    t_bug = UnifiedTracker()
    r = HookRegistry()
    r.install_all(t_bug)
    try:
        run(t_bug, buggy=True)
    finally:
        r.uninstall_all()
        HookRegistry._globally_installed.clear()
    an = LineageAnalyzer(t_bug)
    an.set_baseline(baseline)
    return an


class TestEncodingBug:
    def test_localizes_to_get_dummies(self):
        an = _baseline_then_buggy(_run_encoding)
        cause = an.localize_root_cause("f1_score")
        assert cause.root_operation == "get_dummies"
        assert cause.root_step_index == 0
        assert cause.evidence["n_columns_introduced"] == 9      # 10 ids, drop_first
        assert cause.evidence["columns_missing"] == ["region_north", "region_south", "region_west"]
        assert "never saw" in cause.explanation

    def test_anomalies_name_the_columns(self):
        an = _baseline_then_buggy(_run_encoding)
        by_metric = {a.metric: a for a in an.detect_anomalies()}
        intro = by_metric["columns_introduced"]
        assert intro.operation == "get_dummies" and intro.step_index == 0
        assert intro.deviation == 9
        assert "customer_id_1" in intro.message
        missing = by_metric["columns_missing"]
        assert missing.operation == "get_dummies"
        assert "region_north" in missing.message

    def test_downstream_drop_is_not_blamed(self):
        an = _baseline_then_buggy(_run_encoding)
        cause = an.localize_root_cause("f1_score")
        # The drop that follows inherits the changed column set and must
        # score strictly lower than the operation that caused it.
        assert cause.root_operation != "drop"


class TestLeakageBug:
    def test_localizes_to_first_op_carrying_the_label(self):
        an = _baseline_then_buggy(_run_leakage)
        cause = an.localize_root_cause("f1_score")
        assert cause.root_operation == "get_dummies"
        assert cause.root_step_index == 0
        assert cause.evidence["columns_retained"] == ["y"]
        assert cause.evidence["retained_removed_by"] == ["drop"]
        assert "removed by drop in the baseline" in cause.explanation

    def test_retained_anomaly_is_critical_and_names_the_dropper(self):
        an = _baseline_then_buggy(_run_leakage)
        retained = [a for a in an.detect_anomalies() if a.metric == "columns_retained"]
        assert len(retained) == 1
        a = retained[0]
        assert a.severity == "critical"
        assert a.operation == "get_dummies" and a.step_index == 0
        assert "y removed by drop" in a.message

    def test_no_spurious_missing_columns(self):
        # 'region' is consumed by get_dummies in both runs; it is not a
        # column the baseline *created*, so it must not be reported as
        # missing just because the buggy run has no record before
        # get_dummies.
        an = _baseline_then_buggy(_run_leakage)
        assert not [a for a in an.detect_anomalies() if a.metric == "columns_missing"]


class TestNoFalsePositives:
    def test_inserted_operation_does_not_flag_inherited_columns(self):
        def run(tracker, buggy):
            df = _frame()
            if buggy:
                df = df.dropna()           # inserted op exposes raw columns earlier
            X = pd.get_dummies(df.drop(columns=["y"]), columns=["region"], dtype=float)
            _metric(tracker, "f1_score", 0.9)
        an = _baseline_then_buggy(run)
        metrics = {a.metric for a in an.detect_anomalies()}
        assert not metrics & {"columns_introduced", "columns_retained", "columns_missing"}

    def test_identical_runs_produce_no_membership_anomalies(self):
        an = _baseline_then_buggy(lambda t, buggy: _run_encoding(t, buggy=False))
        metrics = {a.metric for a in an.detect_anomalies()}
        assert not metrics & {"columns_introduced", "columns_retained", "columns_missing"}

    def test_threshold_disables_membership(self):
        an = _baseline_then_buggy(_run_encoding)
        an._thresholds["column_membership"] = False
        metrics = {a.metric for a in an.detect_anomalies()}
        assert not metrics & {"columns_introduced", "columns_retained", "columns_missing"}
        cause = an.localize_root_cause("f1_score")
        assert "columns_introduced" not in cause.evidence
