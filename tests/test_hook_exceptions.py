"""A hooked call that raises must not hide the next call or change the result."""

import pandas as pd
import pytest

from autolineage.core.tracker import UnifiedTracker
from autolineage.hooks.registry import HookRegistry


@pytest.fixture
def tracker():
    tracker = UnifiedTracker()
    registry = HookRegistry()
    registry.install_all(tracker)
    try:
        yield tracker
    finally:
        registry.uninstall_all()


def test_a_failing_pandas_call_does_not_hide_the_next(tracker):
    frame = pd.DataFrame({"a": [1.0, None, 3.0]})
    with pytest.raises(ValueError):
        frame.dropna(axis="not-an-axis")
    kept = frame.dropna()
    assert list(kept["a"]) == [1.0, 3.0]
    assert [rec.operation for rec in tracker.records].count("dropna") == 1


def test_dropna_returns_the_same_rows_as_the_unhooked_method(tracker):
    frame = pd.DataFrame({"a": [1.0, None, 3.0]})
    hooked = frame.dropna()
    plain = pd.DataFrame.dropna.__wrapped__(pd.DataFrame({"a": [1.0, None, 3.0]}))
    pd.testing.assert_frame_equal(hooked, plain)
    assert [rec.operation for rec in tracker.records] == ["dropna"]


def test_a_failing_fit_does_not_hide_the_next(tracker):
    from sklearn.linear_model import LogisticRegression

    model = LogisticRegression()
    with pytest.raises(ValueError):
        model.fit([[1.0, 2.0], [3.0, 4.0]], [0, 1, 2])
    model.fit([[1.0], [2.0], [3.0], [4.0]], [0, 1, 0, 1])
    fits = [rec for rec in tracker.records if rec.operation == "LogisticRegression.fit"]
    assert len(fits) == 1
