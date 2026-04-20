"""Tests for v2 plugin architecture, unified tracker, and analyzer."""

import pytest
import pandas as pd
import numpy as np


class TestTransformationRecord:
    def test_creation(self):
        from autolineage.core import TransformationRecord
        rec = TransformationRecord(library="pandas", category="transform",
            operation="dropna", rows_before=100, rows_after=90)
        assert rec.library == "pandas"
        assert rec.row_delta == -10

    def test_col_delta(self):
        from autolineage.core import TransformationRecord
        rec = TransformationRecord(columns_added=["a", "b"], columns_removed=["c"])
        assert rec.col_delta == 1

    def test_to_dict(self):
        from autolineage.core import TransformationRecord
        d = TransformationRecord(library="sklearn", operation="fit").to_dict()
        assert d['library'] == 'sklearn'

    def test_repr(self):
        from autolineage.core import TransformationRecord
        rec = TransformationRecord(library="pandas", operation="dropna",
            input_shape=(100, 5), output_shape=(90, 5))
        assert "pandas.dropna" in repr(rec)


class TestUnifiedTracker:
    def test_assign_and_get_id_dataframe(self):
        from autolineage.core.tracker import UnifiedTracker
        t = UnifiedTracker()
        df = pd.DataFrame({'a': [1, 2]})
        lid = t.assign_id(df, source="test")
        assert t.get_id(df) == lid

    def test_assign_and_get_id_array(self):
        from autolineage.core.tracker import UnifiedTracker
        t = UnifiedTracker()
        arr = np.array([1, 2, 3])
        lid = t.assign_id(arr, source="test")
        assert t.get_id(arr) == lid

    def test_get_or_assign(self):
        from autolineage.core.tracker import UnifiedTracker
        t = UnifiedTracker()
        df = pd.DataFrame({'a': [1]})
        lid1 = t.get_or_assign(df, source="test")
        lid2 = t.get_or_assign(df, source="test")
        assert lid1 == lid2

    def test_record_and_summary(self):
        from autolineage.core.tracker import UnifiedTracker
        from autolineage.core import TransformationRecord
        t = UnifiedTracker()
        t.record(TransformationRecord(library="pandas", operation="dropna", rows_before=100, rows_after=90))
        s = t.get_summary()
        assert s['total_records'] == 1
        assert 'pandas' in s['libraries_tracked']

    def test_get_chain(self):
        from autolineage.core.tracker import UnifiedTracker
        from autolineage.core import TransformationRecord
        t = UnifiedTracker()
        t.record(TransformationRecord(operation="read", parent_ids=[], child_id="a"))
        t.record(TransformationRecord(operation="dropna", parent_ids=["a"], child_id="b"))
        t.record(TransformationRecord(operation="filter", parent_ids=["b"], child_id="c"))
        chain = t.get_chain("c")
        assert len(chain) == 3
        assert chain[0].operation == "read"

    def test_full_graph(self):
        from autolineage.core.tracker import UnifiedTracker
        from autolineage.core import TransformationRecord
        t = UnifiedTracker()
        t.record(TransformationRecord(operation="test"))
        g = t.get_full_graph()
        assert len(g['edges']) == 1

    def test_timing_profile(self):
        from autolineage.core.tracker import UnifiedTracker
        from autolineage.core import TransformationRecord
        t = UnifiedTracker()
        t.record(TransformationRecord(operation="slow_op", duration_ms=500, library="pandas"))
        t.record(TransformationRecord(operation="fast_op", duration_ms=10, library="pandas"))
        t.record(TransformationRecord(operation="no_time"))
        profile = t.get_timing_profile()
        assert len(profile) == 2
        assert profile[0]['operation'] == 'slow_op'
        assert profile[0]['percent_of_total'] > 90


class TestHookRegistry:
    def test_install_discovers_pandas(self):
        from autolineage.core.tracker import UnifiedTracker
        from autolineage.hooks.registry import HookRegistry
        HookRegistry._globally_installed.clear()
        t = UnifiedTracker()
        r = HookRegistry()
        installed = r.install_all(t)
        names = [n for n, _ in installed]
        assert 'pandas-io' in names
        r.uninstall_all()

    def test_double_install_safe(self):
        from autolineage.core.tracker import UnifiedTracker
        from autolineage.hooks.registry import HookRegistry
        HookRegistry._globally_installed.clear()
        t = UnifiedTracker()
        r1 = HookRegistry()
        r1.install_all(t)
        r2 = HookRegistry()
        installed2 = r2.install_all(t)
        # Second install should return empty - already installed
        assert len(installed2) == 0
        r1.uninstall_all()

    def test_uninstall_allows_reinstall(self):
        from autolineage.core.tracker import UnifiedTracker
        from autolineage.hooks.registry import HookRegistry
        HookRegistry._globally_installed.clear()
        t = UnifiedTracker()
        r = HookRegistry()
        r.install_all(t)
        r.uninstall_all()
        # Should be able to reinstall
        r2 = HookRegistry()
        installed = r2.install_all(t)
        assert len(installed) > 0
        r2.uninstall_all()


class TestPandasHooksV2:
    @pytest.fixture(autouse=True)
    def setup(self):
        from autolineage.core.tracker import UnifiedTracker
        from autolineage.hooks.registry import HookRegistry
        HookRegistry._globally_installed.clear()
        self.tracker = UnifiedTracker()
        self.registry = HookRegistry()
        self.registry.install_all(self.tracker)
        yield
        self.registry.uninstall_all()

    def test_dropna(self):
        df = pd.DataFrame({'a': [1, None, 3]})
        self.tracker.assign_id(df, source="test")
        df.dropna()
        assert any(r.operation == 'dropna' for r in self.tracker.records)

    def test_filter(self):
        df = pd.DataFrame({'a': [1, 2, 3, 4, 5]})
        self.tracker.assign_id(df, source="test")
        df[df['a'] > 2]
        assert any(r.operation == 'filter' for r in self.tracker.records)

    def test_merge(self):
        df1 = pd.DataFrame({'k': [1, 2], 'v1': ['a', 'b']})
        df2 = pd.DataFrame({'k': [1, 2], 'v2': ['c', 'd']})
        df1.merge(df2, on='k')
        assert any(r.operation == 'merge' for r in self.tracker.records)

    def test_chained(self):
        df = pd.DataFrame({'a': [1, None, 3, 4], 'b': ['x', 'y', 'z', 'x'], 'c': [10, 20, 30, 40]})
        self.tracker.assign_id(df, source="raw")
        df = df.dropna()
        df = df[df['a'] > 2]
        df = df.assign(d=df['c'] * 2)
        df.groupby('b')['d'].sum()
        assert len(self.tracker.records) >= 4

    def test_write_keyword_path(self):
        """BUG 1 fix: to_csv(path_or_buf=...) should not crash."""
        import tempfile, os
        df = pd.DataFrame({'a': [1, 2]})
        self.tracker.assign_id(df, source="test")
        path = os.path.join(tempfile.mkdtemp(), 'test.csv')
        df.to_csv(path)  # positional
        df.to_csv(path_or_buf=path)  # keyword - was crashing before fix
        assert any(r.operation == 'to_csv' for r in self.tracker.records)

    def test_content_hash_populated(self):
        """GAP 3 fix: records should have content_hash."""
        df = pd.DataFrame({'a': [1, 2, 3]})
        self.tracker.assign_id(df, source="test")
        df.dropna()
        recs = [r for r in self.tracker.records if r.operation == 'dropna']
        assert len(recs) > 0
        assert recs[0].content_hash is not None


class TestSklearnHooksV2:
    @pytest.fixture(autouse=True)
    def setup(self):
        pytest.importorskip("sklearn")
        from autolineage.core.tracker import UnifiedTracker
        from autolineage.hooks.registry import HookRegistry
        HookRegistry._globally_installed.clear()
        self.tracker = UnifiedTracker()
        self.registry = HookRegistry()
        self.registry.install_all(self.tracker)
        yield
        self.registry.uninstall_all()

    def test_train_test_split(self):
        from sklearn.model_selection import train_test_split
        X = np.random.randn(100, 5)
        y = np.random.randint(0, 2, 100)
        train_test_split(X, y, test_size=0.2)
        assert any(r.operation == 'train_test_split' for r in self.tracker.records)

    def test_fit_predict(self):
        from sklearn.ensemble import RandomForestClassifier
        X, y = np.random.randn(100, 5), np.random.randint(0, 2, 100)
        m = RandomForestClassifier(n_estimators=5, random_state=42)
        m.fit(X, y)
        m.predict(X)
        assert any('fit' in r.operation and 'RandomForest' in r.operation for r in self.tracker.records)
        assert any('predict' in r.operation and 'RandomForest' in r.operation for r in self.tracker.records)

    def test_reentrancy_depth(self):
        """BUG 4 fix: RF.predict should not track 100 internal DT.predict calls."""
        from sklearn.ensemble import RandomForestClassifier
        X, y = np.random.randn(50, 3), np.random.randint(0, 2, 50)
        m = RandomForestClassifier(n_estimators=10, random_state=42)
        m.fit(X, y)
        m.predict(X)
        pred_recs = [r for r in self.tracker.records if 'predict' in r.operation]
        # Should have RF-level predictions only, NOT 10x DecisionTree.predict
        dt_preds = [r for r in pred_recs if 'DecisionTree' in r.operation]
        assert len(dt_preds) == 0, f"Internal DT.predict leaked: {dt_preds}"
        # RF.predict may call predict_proba internally — that's fine at depth 1
        rf_preds = [r for r in pred_recs if 'RandomForest' in r.operation]
        assert len(rf_preds) >= 1

    def test_pipeline_shows_internals(self):
        """BUG 4 fix: Pipeline should show inner component operations."""
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.ensemble import RandomForestClassifier
        X, y = np.random.randn(100, 5), np.random.randint(0, 2, 100)
        pipe = Pipeline([('scaler', StandardScaler()), ('clf', RandomForestClassifier(n_estimators=5, random_state=42))])
        pipe.fit(X, y)
        pipe.predict(X)
        ops = [r.operation for r in self.tracker.records]
        # Should see Pipeline.fit AND inner StandardScaler + RF operations
        assert any('Pipeline' in o for o in ops)
        # Inner scaler should be visible (depth 1, allowed)
        assert any('StandardScaler' in o for o in ops)

    def test_metrics(self):
        from sklearn.metrics import accuracy_score, f1_score
        y_true, y_pred = [0, 1, 1, 0], [0, 1, 0, 0]
        accuracy_score(y_true, y_pred)
        f1_score(y_true, y_pred)
        eval_recs = [r for r in self.tracker.records if r.category == 'evaluate']
        assert len(eval_recs) == 2

    def test_full_ml_pipeline(self):
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score
        X, y = np.random.randn(200, 5), np.random.randint(0, 2, 200)
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2)
        s = StandardScaler()
        X_tr_s = s.fit_transform(X_tr)
        X_te_s = s.transform(X_te)
        m = RandomForestClassifier(n_estimators=5, random_state=42)
        m.fit(X_tr_s, y_tr)
        y_p = m.predict(X_te_s)
        accuracy_score(y_te, y_p)
        cats = set(r.category for r in self.tracker.records)
        for expected in ('split', 'preprocess', 'train', 'predict', 'evaluate'):
            assert expected in cats, f"Missing category: {expected}"


class TestLineageAnalyzer:
    def _make_tracker(self, records_data):
        from autolineage.core.tracker import UnifiedTracker
        from autolineage.core import TransformationRecord
        t = UnifiedTracker()
        for rd in records_data:
            t.record(TransformationRecord(**rd))
        return t

    def test_fingerprint(self):
        from autolineage.core.analyzer import LineageAnalyzer
        t = self._make_tracker([
            {'operation': 'dropna', 'rows_before': 100, 'rows_after': 90},
            {'operation': 'filter', 'rows_before': 90, 'rows_after': 50},
            {'category': 'evaluate', 'operation': 'accuracy_score',
             'metadata': {'metric_name': 'accuracy_score', 'metric_value': 0.85}},
        ])
        fp = LineageAnalyzer(t).fingerprint()
        assert fp.total_records == 3
        assert fp.metrics['accuracy_score'] == 0.85
        # Check new key format: operation:occurrence
        assert 'dropna:1' in fp.row_deltas
        assert 'filter:1' in fp.row_deltas

    def test_self_anomaly_large_drop(self):
        from autolineage.core.analyzer import LineageAnalyzer
        t = self._make_tracker([{'operation': 'filter', 'rows_before': 10000, 'rows_after': 100}])
        anomalies = LineageAnalyzer(t).detect_anomalies()
        assert len(anomalies) >= 1
        assert anomalies[0].severity == 'critical'

    def test_self_anomaly_zero_metric(self):
        from autolineage.core.analyzer import LineageAnalyzer
        t = self._make_tracker([
            {'category': 'evaluate', 'operation': 'f1_score',
             'metadata': {'metric_name': 'f1_score', 'metric_value': 0.0}}])
        anomalies = LineageAnalyzer(t).detect_anomalies()
        assert any('0.0' in a.message for a in anomalies)

    def test_self_anomaly_perfect_metric(self):
        from autolineage.core.analyzer import LineageAnalyzer
        t = self._make_tracker([
            {'category': 'evaluate', 'operation': 'accuracy_score',
             'metadata': {'metric_name': 'accuracy_score', 'metric_value': 1.0}}])
        anomalies = LineageAnalyzer(t).detect_anomalies()
        assert any('1.0' in a.message or 'leakage' in a.message for a in anomalies)

    def test_baseline_row_delta(self):
        from autolineage.core.analyzer import LineageAnalyzer, RunFingerprint
        t = self._make_tracker([{'operation': 'filter', 'rows_before': 1000, 'rows_after': 200}])
        bl = RunFingerprint(total_records=1, operation_sequence=['filter'],
            row_deltas={'filter:1': -100})  # new key format
        anomalies = LineageAnalyzer(t).detect_anomalies(baseline=bl)
        assert any(a.metric == 'row_delta' for a in anomalies)

    def test_baseline_metric_drop(self):
        from autolineage.core.analyzer import LineageAnalyzer, RunFingerprint
        t = self._make_tracker([
            {'category': 'evaluate', 'operation': 'accuracy',
             'metadata': {'metric_name': 'accuracy', 'metric_value': 0.60}}])
        bl = RunFingerprint(total_records=1, operation_sequence=['accuracy'],
            metrics={'accuracy': 0.90})
        anomalies = LineageAnalyzer(t).detect_anomalies(baseline=bl)
        assert any(a.metric == 'accuracy' for a in anomalies)

    def test_baseline_missing_operation(self):
        from autolineage.core.analyzer import LineageAnalyzer, RunFingerprint
        t = self._make_tracker([{'operation': 'dropna'}])
        bl = RunFingerprint(total_records=2, operation_sequence=['dropna', 'filter'])
        anomalies = LineageAnalyzer(t).detect_anomalies(baseline=bl)
        assert any(a.metric == 'operation_missing' for a in anomalies)

    def test_root_cause_without_baseline(self):
        from autolineage.core.analyzer import LineageAnalyzer
        t = self._make_tracker([
            {'operation': 'read_csv', 'rows_before': None, 'rows_after': 10000},
            {'operation': 'filter', 'rows_before': 10000, 'rows_after': 50},
            {'operation': 'dropna', 'rows_before': 50, 'rows_after': 48},
            {'category': 'evaluate', 'operation': 'f1_score',
             'metadata': {'metric_name': 'f1_score', 'metric_value': 0.0}},
        ])
        cause = LineageAnalyzer(t).localize_root_cause()
        assert cause is not None
        assert cause.root_operation == 'filter'
        assert cause.impact_score > 0.9

    def test_root_cause_with_baseline(self):
        from autolineage.core.analyzer import LineageAnalyzer, RunFingerprint
        t = self._make_tracker([
            {'operation': 'filter', 'rows_before': 10000, 'rows_after': 2000},
            {'operation': 'dropna', 'rows_before': 2000, 'rows_after': 1900},
            {'category': 'evaluate', 'operation': 'accuracy',
             'metadata': {'metric_name': 'accuracy', 'metric_value': 0.60}},
        ])
        bl = RunFingerprint(total_records=3, operation_sequence=['filter', 'dropna', 'accuracy'],
            row_deltas={'filter:1': -1000, 'dropna:1': -100},  # new key format
            metrics={'accuracy': 0.92})
        cause = LineageAnalyzer(t).localize_root_cause(baseline=bl)
        assert cause is not None
        assert cause.root_operation == 'filter'

    def test_save_and_load_fingerprint(self, tmp_path):
        from autolineage.core.analyzer import LineageAnalyzer
        t = self._make_tracker([{'operation': 'dropna', 'rows_before': 100, 'rows_after': 90}])
        a = LineageAnalyzer(t)
        path = str(tmp_path / "fp.json")
        a.save_fingerprint(path)
        assert a.load_baseline(path)
        assert a._baseline is not None
        assert a._baseline.total_records == 1
