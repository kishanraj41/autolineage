"""Calls made on several threads at once are all recorded, and pool threads
that a library starts stay out of the graph."""

import threading

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


def test_concurrent_pandas_calls_are_all_recorded(tracker):
    frame = pd.DataFrame({"a": list(range(5000)), "b": [1.0, None] * 2500})
    threads, calls = 8, 25
    start = threading.Barrier(threads)

    def work():
        start.wait()
        for _ in range(calls):
            frame.sort_values("a", ascending=False).dropna()

    workers = [threading.Thread(target=work) for _ in range(threads)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    operations = [rec.operation for rec in tracker.records]
    assert operations.count("sort_values") == threads * calls
    assert operations.count("dropna") == threads * calls
    assert set(operations) == {"sort_values", "dropna"}


def test_a_nested_call_on_another_thread_stays_nested(tracker):
    """Depth is per thread: a thread held inside ``sort_values`` does not make
    a call on the main thread look nested, and each call's internals stay hidden."""
    frame = pd.DataFrame({"a": [1, 1, 2, 3] * 500})
    inside = threading.Event()
    release = threading.Event()

    def slow_key(series):
        inside.set()
        release.wait(timeout=10)
        return series

    def holder():
        frame.sort_values("a", key=slow_key)

    thread = threading.Thread(target=holder)
    thread.start()
    assert inside.wait(timeout=10)
    try:
        frame.drop_duplicates()
    finally:
        release.set()
        thread.join()

    operations = sorted(rec.operation for rec in tracker.records)
    assert operations == ["drop_duplicates", "sort_values"]


def test_forest_pool_threads_are_not_recorded(tracker):
    pytest.importorskip("sklearn")
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier

    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(200, 4)), columns=list("abcd"))
    y = (X["a"] > 0).astype(int)
    model = RandomForestClassifier(n_estimators=8, n_jobs=2, random_state=0)
    model.fit(X, y)
    model.predict(X)
    model.predict_proba(X)

    operations = [rec.operation for rec in tracker.records if rec.library == "sklearn"]
    assert operations == [
        "RandomForestClassifier.__init__",
        "RandomForestClassifier.fit",
        "RandomForestClassifier.predict",
        "RandomForestClassifier.predict_proba",
    ]


def test_estimators_fitted_on_user_threads_are_recorded(tracker):
    pytest.importorskip("sklearn")
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    rng = np.random.default_rng(0)
    X = rng.normal(size=(120, 3))
    y = (X[:, 0] > 0).astype(int)
    threads = 6
    start = threading.Barrier(threads)

    def work():
        start.wait()
        LogisticRegression().fit(X, y).predict(X)

    workers = [threading.Thread(target=work) for _ in range(threads)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    operations = [rec.operation for rec in tracker.records]
    assert operations.count("LogisticRegression.fit") == threads
    assert operations.count("LogisticRegression.predict") == threads
    assert operations.count("LogisticRegression.__init__") == threads
