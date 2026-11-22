"""The published hook counts are the numbers install_all returns."""

import pytest

from autolineage.core.tracker import UnifiedTracker
from autolineage.hooks.registry import HookRegistry


def _installed():
    tracker = UnifiedTracker()
    registry = HookRegistry()
    try:
        return dict(registry.install_all(tracker))
    finally:
        registry.uninstall_all()


def test_pandas_and_sklearn_hook_counts():
    installed = _installed()
    assert installed["pandas-io"] == 10
    assert installed["pandas-transforms"] == 60
    assert installed["sklearn"] == 235


def test_pyspark_hook_count():
    pyspark = pytest.importorskip("pyspark")
    installed = _installed()
    assert installed["pyspark"] == 49, pyspark.__version__
