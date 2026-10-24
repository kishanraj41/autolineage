"""Pipeline lines that run in a child process are recorded after join.

``RF.py`` calls ``train_test_split``, ``RandomForestClassifier``, ``fit``,
``predict``, ``accuracy_score``, and ``recall_score`` inside
``multiprocess.Process``. Those names are imported before the child
installs hooks, so the test imports them the same way.
"""

import inspect

import pandas as pd
import pytest
from sklearn.metrics import accuracy_score, recall_score
from sklearn.model_selection import train_test_split

from autolineage.core.tracker import UnifiedTracker
from autolineage.hooks.registry import HookRegistry

_FRAME = pd.DataFrame({
    "a": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
    "b": [0, 1, 0, 1, 0, 1, 0, 1],
})


def _pipeline_in_child():
    from sklearn.ensemble import RandomForestClassifier
    frame = _FRAME.dropna()
    X = frame[["a"]]
    y = frame["b"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=0, stratify=y)
    clf = RandomForestClassifier(n_estimators=2, random_state=0)
    clf.fit(X_train, y_train)
    pred = clf.predict(X_test)
    accuracy_score(y_test, pred)
    recall_score(y_test, pred)


def _line_of(snippet):
    lines, start = inspect.getsourcelines(_pipeline_in_child)
    offset = next(i for i, line in enumerate(lines) if snippet in line)
    return start + offset


@pytest.fixture
def hooked():
    tracker = UnifiedTracker()
    registry = HookRegistry()
    registry.install_all(tracker)
    try:
        yield tracker
    finally:
        registry.uninstall_all()


@pytest.mark.parametrize("mod_name", ["multiprocessing", "multiprocess"])
def test_child_pipeline_lines_arrive_on_join(hooked, mod_name):
    mod = pytest.importorskip(mod_name)
    proc = mod.Process(target=_pipeline_in_child)
    proc.start()
    proc.join(timeout=60)
    assert proc.exitcode == 0
    ops = [r.operation for r in hooked.records]
    for expected in (
        "train_test_split",
        "RandomForestClassifier.__init__",
        "RandomForestClassifier.fit",
        "RandomForestClassifier.predict",
        "accuracy_score",
        "recall_score",
    ):
        assert expected in ops, ops
    split = next(r for r in hooked.records if r.operation == "train_test_split")
    assert split.metadata["source_line"] == _line_of("train_test_split(")
    assert split.metadata["source_file"].endswith("test_process_capture.py")


def test_uninstall_restores_process_and_drops_later_children():
    import multiprocessing
    tracker = UnifiedTracker()
    registry = HookRegistry()
    registry.install_all(tracker)
    registry.uninstall_all()
    assert not getattr(multiprocessing.Process.__init__, "_autolineage_wrapped", False)
    proc = multiprocessing.Process(target=_pipeline_in_child)
    proc.start()
    proc.join(timeout=60)
    assert proc.exitcode == 0
    assert tracker.records == []
