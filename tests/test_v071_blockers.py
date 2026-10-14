"""Review blockers for the v0.7.1 diff. Both fail on that diff."""

import numpy as np
import pandas as pd

from autolineage.core.analyzer import LineageAnalyzer
from autolineage.core.tracker import UnifiedTracker
from autolineage.hooks.registry import HookRegistry


def _hooked():
    HookRegistry._globally_installed.clear()
    tracker = UnifiedTracker()
    registry = HookRegistry()
    registry.install_all(tracker)
    return tracker, registry


def test_nine_step_chain_has_distinct_child_ids():
    """Each derived frame gets its own lineage id, parented on the previous one."""
    tracker, registry = _hooked()
    fired = []
    tracker.register_assign_id_callback(lambda obj, lid: fired.append((id(obj), lid)))
    try:
        df = pd.DataFrame({"a": [1.0, None, 3, 4], "b": [1, 2, 3, 3], "k": list("xyxy")})
        x = df.fillna(0)
        x = x.sort_values("a")
        x = x.rename(columns={"a": "A"})
        x = x.drop_duplicates()
        x = x[x.b > 1]
        x = x.query("b>2")
        x = x.drop(columns=["k"])
        x = x.reset_index(drop=True)
        x = x.assign(c=1)
        records = list(tracker.records)
        assert len(records) == 9
        child_ids = [rec.child_id for rec in records]
        assert len(set(child_ids)) == 9
        for earlier, later in zip(records, records[1:]):
            assert later.parent_ids == [earlier.child_id]
        assert all(rec.child_id not in rec.parent_ids for rec in records)
        # assign_id is what RudriQ listens to. Every child id has to be announced.
        announced = {lid for _obj, lid in fired}
        assert set(child_ids) <= announced
    finally:
        registry.uninstall_all()
        HookRegistry._globally_installed.clear()


def test_inserted_filter_is_blamed_when_baseline_already_filters():
    """A second boolean filter is an insert, even though the type is not new."""
    tracker, registry = _hooked()

    def run(insert):
        tracker.records.clear()
        rng = np.random.default_rng(0)
        n = 7000
        frame = pd.DataFrame({
            "tenure": rng.integers(0, 72, n),
            "charges": rng.normal(70, 20, n),
            "senior": rng.integers(0, 2, n),
        })
        probability = 1 / (1 + np.exp(0.08 * frame.tenure - 1.5))
        frame["churn"] = (rng.random(n) < probability).astype(int)
        frame = frame[frame.charges > 0]
        if insert:
            frame = frame[frame.tenure >= 24]
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import f1_score
        from sklearn.model_selection import train_test_split
        features, target = frame[["tenure", "charges", "senior"]], frame["churn"]
        x_train, x_test, y_train, y_test = train_test_split(
            features, target, test_size=0.2, random_state=0,
        )
        predicted = LogisticRegression(max_iter=500).fit(x_train, y_train).predict(x_test)
        f1_score(y_test, predicted)
        return LineageAnalyzer(tracker)

    try:
        baseline = run(False).fingerprint()
        current = run(True)
        assert current.detect_anomalies(baseline)
        root = current.localize_root_cause(baseline=baseline)
        assert root is not None
        assert root.root_operation == "filter"
        assert "introduced_row_drop" in root.evidence
    finally:
        registry.uninstall_all()
        HookRegistry._globally_installed.clear()
