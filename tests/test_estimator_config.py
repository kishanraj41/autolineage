"""Estimator and preprocessor construction is recorded at the user's line.

On the development scripts of the real benchmark, constructor lines
(Pipeline, ColumnTransformer, SimpleImputer, OneHotEncoder, GridSearchCV,
the classifiers) were the largest group of pipeline lines with no record.
The ``change_encoding`` fault edits a constructor argument, so without a
record on that line it can never be localized.
"""

import inspect
import os

import numpy as np
import pandas as pd
import pytest

sklearn = pytest.importorskip("sklearn")

from autolineage.core.tracker import UnifiedTracker  # noqa: E402
from autolineage.hooks.registry import HookRegistry  # noqa: E402


def _configure(tracker):
    return [r for r in tracker.records if r.category == "configure"]


@pytest.fixture
def hooked():
    tracker = UnifiedTracker()
    registry = HookRegistry()
    registry.install_all(tracker)
    try:
        yield tracker
    finally:
        registry.uninstall_all()


def test_constructor_records_params_and_caller_line(hooked):
    from sklearn.preprocessing import OneHotEncoder
    line = inspect.currentframe().f_lineno + 1
    enc = OneHotEncoder(handle_unknown="ignore")
    recs = _configure(hooked)
    assert [r.operation for r in recs] == ["OneHotEncoder.__init__"]
    assert recs[0].parameters["handle_unknown"] == "ignore"
    assert recs[0].metadata["source_line"] == line
    assert recs[0].metadata["source_file"] == os.path.abspath(__file__)
    assert enc.get_params()["handle_unknown"] == "ignore"


def test_nested_constructors_each_get_their_own_line(hooked):
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    start = inspect.currentframe().f_lineno + 1
    pipe = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    lines = {r.operation: r.metadata["source_line"] for r in _configure(hooked)}
    assert lines == {
        "Pipeline.__init__": start,
        "SimpleImputer.__init__": start + 1,
        "StandardScaler.__init__": start + 2,
    }
    assert pipe.named_steps["imputer"].strategy == "median"


def test_library_internal_constructions_are_not_recorded(hooked):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GridSearchCV
    rng = np.random.RandomState(0)
    X = pd.DataFrame(rng.rand(60, 3), columns=["a", "b", "c"])
    y = pd.Series(rng.randint(0, 2, 60))
    RandomForestClassifier(n_estimators=5, random_state=0).fit(X, y)
    GridSearchCV(LogisticRegression(), {"C": [0.1, 1.0]}, cv=3).fit(X, y)
    ops = sorted(r.operation for r in _configure(hooked))
    # Three user calls. The trees, the cloned LogisticRegressions and the
    # refit inside the search are sklearn's own and stay out.
    assert ops == ["GridSearchCV.__init__", "LogisticRegression.__init__",
                   "RandomForestClassifier.__init__"]


def test_get_params_clone_and_repr_still_work(hooked):
    from sklearn.base import clone
    from sklearn.linear_model import LogisticRegression
    est = LogisticRegression(C=0.5, max_iter=200)
    copy = clone(est)
    assert copy.get_params() == est.get_params()
    assert "C=0.5" in repr(est)
    assert copy.set_params(C=2.0).C == 2.0


def test_uninstall_restores_the_original_init():
    from sklearn.preprocessing import OneHotEncoder
    original = OneHotEncoder.__init__
    tracker = UnifiedTracker()
    registry = HookRegistry()
    registry.install_all(tracker)
    assert OneHotEncoder.__init__ is not original
    registry.uninstall_all()
    assert OneHotEncoder.__init__ is original
    OneHotEncoder()
    assert _configure(tracker) == []


def test_class_without_its_own_init_is_left_alone(hooked):
    from sklearn.preprocessing import LabelEncoder
    assert "__init__" not in LabelEncoder.__dict__
    LabelEncoder().fit(["a", "b"])
    assert LabelEncoder().get_params() == {}
