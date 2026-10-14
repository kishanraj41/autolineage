"""Fixes from the telco churn audit (issues 16-22)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from autolineage.core import TransformationRecord
from autolineage.core.analyzer import LineageAnalyzer, RunFingerprint
from autolineage.core.tracker import UnifiedTracker
from autolineage.hooks.registry import HookRegistry


@pytest.fixture
def hooked():
    HookRegistry._globally_installed.clear()
    tracker = UnifiedTracker()
    registry = HookRegistry()
    registry.install_all(tracker)
    yield tracker
    registry.uninstall_all()
    HookRegistry._globally_installed.clear()


def _rec(**kwargs):
    return TransformationRecord(**kwargs)


def _tracker(*records):
    t = UnifiedTracker()
    for rec in records:
        t.record(rec)
    return t


class TestPathAndInplace:
    def test_pathlib_read_and_write_are_recorded(self, hooked, tmp_path):
        path = Path(tmp_path) / "customers.csv"
        frame = pd.DataFrame({"tenure": [1, 2], "churn": [0, 1]})
        frame.to_csv(path, index=False)
        loaded = pd.read_csv(path)
        ops = [r.operation for r in hooked.records]
        assert "to_csv" in ops
        assert "read_csv" in ops
        assert len(loaded) == 2

    def test_inplace_drop_and_dropna_are_recorded(self, hooked):
        frame = pd.DataFrame({
            "customerID": ["a", "b", "c"],
            "tenure": [1, None, 3],
        })
        frame.dropna(inplace=True)
        frame.drop("customerID", axis=1, inplace=True)
        ops = [r.operation for r in hooked.records]
        assert ops.count("dropna") == 1
        assert ops.count("drop") == 1
        dropna = next(r for r in hooked.records if r.operation == "dropna")
        assert dropna.rows_before == 3
        assert dropna.rows_after == 2
        assert dropna.parameters.get("inplace") is True
        dropped = next(r for r in hooked.records if r.operation == "drop")
        assert "customerID" in (dropped.columns_removed or [])


class TestFilterPredicateAndAssignment:
    def test_boolean_filter_keeps_the_caller_expression(self, hooked):
        frame = pd.DataFrame({"tenure": range(10), "churn": [0, 1] * 5})
        kept = frame[frame["tenure"] >= 4]
        filt = next(r for r in hooked.records if r.operation == "filter")
        assert filt.rows_before == 10
        assert filt.rows_after == len(kept)
        assert "tenure" in filt.parameters.get("expr", "")

    def test_series_map_and_column_assign(self, hooked):
        frame = pd.DataFrame({"Churn": ["Yes", "No", "Yes"]})
        frame["Churn"] = frame["Churn"].map({"Yes": 1, "No": 0})
        frame["TotalCharges"] = [10.0, 20.0, 30.0]
        ops = [r.operation for r in hooked.records]
        assert "map" in ops
        mapped = next(r for r in hooked.records if r.operation == "map")
        assert mapped.parameters.get("column") == "Churn"
        assigns = [r for r in hooked.records if r.operation == "assign"]
        assert {r.parameters.get("column") for r in assigns} >= {"Churn", "TotalCharges"}


class TestRepeatedMetrics:
    def test_each_accuracy_call_is_kept_and_compared(self):
        baseline = _tracker(
            _rec(category="evaluate", operation="accuracy_score",
                 metadata={"metric_name": "accuracy_score", "metric_value": 0.90}),
            _rec(category="evaluate", operation="accuracy_score",
                 metadata={"metric_name": "accuracy_score", "metric_value": 0.80}),
        )
        current = _tracker(
            _rec(category="evaluate", operation="accuracy_score",
                 metadata={"metric_name": "accuracy_score", "metric_value": 0.50}),
            _rec(category="evaluate", operation="accuracy_score",
                 metadata={"metric_name": "accuracy_score", "metric_value": 0.80}),
        )
        bl = LineageAnalyzer(baseline).fingerprint()
        an = LineageAnalyzer(current)
        assert bl.metrics["accuracy_score"] == 0.80
        assert bl.metric_runs["accuracy_score"] == [0.90, 0.80]
        anomalies = an.detect_anomalies(baseline=bl)
        messages = [a.message for a in anomalies if a.metric == "accuracy_score"]
        assert any("#1" in m and "0.9000" in m and "0.5000" in m for m in messages)
        assert not any("#2" in m and "dropped" in m for m in messages)


class TestRootCauseOfInsertedFilter:
    def _runs(self):
        baseline = _tracker(
            _rec(operation="train_test_split", rows_before=1000, rows_after=800),
            _rec(category="evaluate", operation="f1_score",
                 metadata={"metric_name": "f1_score", "metric_value": 0.608}),
            _rec(category="evaluate", operation="accuracy_score",
                 metadata={"metric_name": "accuracy_score", "metric_value": 0.78}),
        )
        current = _tracker(
            _rec(operation="filter", rows_before=1000, rows_after=500,
                 parameters={"expr": 'frame[frame["tenure"] >= 24]'}),
            _rec(operation="train_test_split", rows_before=500, rows_after=400),
            _rec(category="evaluate", operation="f1_score",
                 metadata={"metric_name": "f1_score", "metric_value": 0.309}),
            _rec(category="evaluate", operation="accuracy_score",
                 metadata={"metric_name": "accuracy_score", "metric_value": 0.87}),
        )
        return LineageAnalyzer(baseline).fingerprint(), current

    def test_f1_drop_is_blamed_on_the_filter_not_the_split(self):
        bl, current = self._runs()
        cause = LineageAnalyzer(current).localize_root_cause("f1_score", baseline=bl)
        assert cause is not None
        assert cause.root_operation == "filter"
        assert "drop" in cause.explanation
        assert "train_test_split" not in cause.explanation

    def test_accuracy_increase_is_not_called_a_degradation(self):
        bl, current = self._runs()
        cause = LineageAnalyzer(current).localize_root_cause("accuracy_score", baseline=bl)
        assert cause is None

    def test_stable_split_ratio_is_not_a_row_anomaly(self):
        bl, current = self._runs()
        anomalies = LineageAnalyzer(current).detect_anomalies(baseline=bl)
        split_rows = [a for a in anomalies if a.operation == "train_test_split" and a.metric == "row_delta"]
        assert split_rows == []
        assert any(a.operation == "filter" and a.metric == "row_delta" for a in anomalies)

    def test_short_durations_are_not_spikes(self):
        baseline = RunFingerprint(
            operation_sequence=["accuracy_score"],
            durations={"accuracy_score:1": 3.0},
        )
        current = _tracker(
            _rec(operation="accuracy_score", duration_ms=16.0),
        )
        anomalies = LineageAnalyzer(current).detect_anomalies(baseline=baseline)
        assert not any(a.metric == "duration_ms" for a in anomalies)


class TestSearchAndReports:
    def test_grid_search_is_one_record(self, hooked):
        from sklearn.model_selection import GridSearchCV
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.linear_model import LogisticRegression

        X = np.random.randn(40, 4)
        y = np.random.randint(0, 2, 40)
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=200)),
        ])
        grid = GridSearchCV(pipe, {"clf__C": [0.1, 1.0]}, cv=2)
        grid.fit(X, y)
        ops = [r.operation for r in hooked.records]
        assert ops.count("GridSearchCV.fit") == 1
        assert "Pipeline.fit" not in ops
        assert "LogisticRegression.fit" not in ops
        assert "LogisticRegression.predict" not in ops
        search = next(r for r in hooked.records if r.operation == "GridSearchCV.fit")
        assert "clf__C" in (search.parameters.get("best_params") or {})

    def test_pipeline_still_records_its_steps(self, hooked):
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.ensemble import RandomForestClassifier

        X = np.random.randn(30, 3)
        y = np.random.randint(0, 2, 30)
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", RandomForestClassifier(n_estimators=5, random_state=0)),
        ])
        pipe.fit(X, y)
        pipe.predict(X)
        ops = [r.operation for r in hooked.records]
        assert "Pipeline.fit" in ops
        assert any(op.startswith("StandardScaler.") for op in ops)
        assert "RandomForestClassifier.fit" in ops
        assert not any("DecisionTree" in op for op in ops)

    def test_classification_report_does_not_leak_label_encoder(self, hooked):
        from sklearn.metrics import classification_report

        classification_report([0, 1, 1, 0], [0, 1, 0, 0])
        ops = [r.operation for r in hooked.records]
        assert ops.count("classification_report") == 1
        assert not any("LabelEncoder" in op for op in ops)
