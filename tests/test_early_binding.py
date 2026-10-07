"""Early-bound imports are rebound to the tracked versions.

`from sklearn.metrics import f1_score` at the top of a script, before the
hooks are installed, used to leave `f1_score` pointing at the unhooked
function: the metric computed correctly but no lineage record was made.
HookRegistry now rebinds such names in __main__ after installing.
"""

import sys
import warnings

import numpy as np
import pandas as pd
import pytest

from autolineage.core.tracker import UnifiedTracker
from autolineage.hooks.registry import HookRegistry, REBIND_ENV_VAR

MAIN = sys.modules["__main__"]


@pytest.fixture
def early(monkeypatch):
    """Yield a helper that binds names into __main__ *before* installing
    hooks, installs, and returns (tracker, registry, captured warnings).
    Cleans up __main__ and the hooks afterwards."""
    injected = []
    registries = []
    HookRegistry._globally_installed.clear()

    def run(**names):
        for k, v in names.items():
            setattr(MAIN, k, v)
            injected.append(k)
        tracker = UnifiedTracker()
        reg = HookRegistry()
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            reg.install_all(tracker)
        registries.append(reg)
        msgs = [str(w.message) for w in captured if issubclass(w.category, UserWarning)]
        return tracker, reg, msgs

    yield run

    for reg in registries:
        reg.uninstall_all()
    HookRegistry._globally_installed.clear()
    for k in injected:
        MAIN.__dict__.pop(k, None)


def _originals():
    """Fresh references to the real functions (hooks not installed)."""
    import sklearn.metrics
    import sklearn.model_selection
    return {
        "f1": sklearn.metrics.f1_score,
        "acc": sklearn.metrics.accuracy_score,
        "tts": sklearn.model_selection.train_test_split,
        "merge": pd.merge,
        "get_dummies": pd.get_dummies,
    }


def _ops(tracker):
    return [r.operation for r in tracker.records]


class TestRebinding:
    def test_metric_imported_early_is_rebound_and_tracked(self, early):
        o = _originals()
        tracker, _, msgs = early(f1_score=o["f1"])
        assert MAIN.f1_score is not o["f1"]
        assert MAIN.f1_score.__wrapped__ is o["f1"]
        assert MAIN.f1_score([0, 1, 1], [0, 1, 0]) == pytest.approx(2 / 3)
        assert "f1_score" in _ops(tracker)
        assert any("rebound in __main__" in m and "f1_score (= sklearn.metrics.f1_score)" in m
                   for m in msgs)

    def test_aliased_import_is_rebound(self, early):
        o = _originals()
        tracker, _, _ = early(acc=o["acc"])
        MAIN.acc([1, 0], [1, 1])
        assert "accuracy_score" in _ops(tracker)

    def test_train_test_split_imported_early(self, early):
        o = _originals()
        tracker, _, _ = early(train_test_split=o["tts"])
        X = pd.DataFrame({"a": range(10)})
        MAIN.train_test_split(X, test_size=0.3, random_state=0)
        assert "train_test_split" in _ops(tracker)

    def test_pandas_module_functions_imported_early(self, early):
        o = _originals()
        tracker, _, msgs = early(merge=o["merge"], get_dummies=o["get_dummies"])
        left = pd.DataFrame({"k": [1, 2], "a": [1, 2]})
        right = pd.DataFrame({"k": [1, 2], "b": [3, 4]})
        MAIN.merge(left, right, on="k")
        MAIN.get_dummies(pd.DataFrame({"c": ["x", "y"]}), columns=["c"])
        ops = _ops(tracker)
        assert "merge" in ops and "get_dummies" in ops
        joined = " ".join(msgs)
        assert "pandas.merge" in joined and "pandas.get_dummies" in joined

    def test_one_warning_lists_every_name(self, early):
        o = _originals()
        _, _, msgs = early(f1_score=o["f1"], merge=o["merge"])
        rebound = [m for m in msgs if "rebound in __main__" in m]
        assert len(rebound) == 1
        assert "f1_score" in rebound[0] and "merge" in rebound[0]


class TestUninstall:
    def test_uninstall_restores_original_binding(self, early):
        o = _originals()
        _, reg, _ = early(f1_score=o["f1"])
        assert MAIN.f1_score is not o["f1"]
        reg.uninstall_all()
        assert MAIN.f1_score is o["f1"]

    def test_uninstall_leaves_user_reassignment_alone(self, early):
        o = _originals()
        _, reg, _ = early(f1_score=o["f1"])

        def mine(*a, **k):
            return 42
        MAIN.f1_score = mine
        reg.uninstall_all()
        assert MAIN.f1_score is mine

    def test_reinstall_after_uninstall_rebinds_again(self, early):
        o = _originals()
        _, reg, _ = early(f1_score=o["f1"])
        reg.uninstall_all()
        HookRegistry._globally_installed.clear()
        tracker = UnifiedTracker()
        reg2 = HookRegistry()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            reg2.install_all(tracker)
        try:
            MAIN.f1_score([0, 1], [0, 1])
            assert "f1_score" in _ops(tracker)
        finally:
            reg2.uninstall_all()
        assert MAIN.f1_score is o["f1"]


class TestOptOutAndNoFalsePositives:
    def test_env_var_disables_rebinding(self, early, monkeypatch):
        monkeypatch.setenv(REBIND_ENV_VAR, "0")
        o = _originals()
        tracker, _, msgs = early(f1_score=o["f1"])
        assert MAIN.f1_score is o["f1"]
        MAIN.f1_score([0, 1], [0, 1])
        assert "f1_score" not in _ops(tracker)
        assert any("will not be tracked" in m for m in msgs)

    def test_unrelated_callables_untouched(self, early):
        def f1_score(*a, **k):           # user's own function, same name
            return 0
        _, _, msgs = early(f1_score=f1_score, helper=np.mean)
        assert MAIN.f1_score is f1_score
        assert MAIN.helper is np.mean
        assert not [m for m in msgs if "imported BEFORE" in m]

    def test_private_names_untouched(self, early):
        o = _originals()
        _, _, _ = early(_f1=o["f1"])
        assert MAIN._f1 is o["f1"]

    def test_no_warning_when_nothing_early(self, early):
        _, _, msgs = early()
        assert not [m for m in msgs if "imported BEFORE" in m]
