"""
Auto-tracking module. Import to enable automatic lineage tracking.

    import autolineage.auto
"""

import atexit
import sys
from typing import Optional, List, Tuple

from .core.tracker import UnifiedTracker
from .hooks.registry import HookRegistry

# Reload-safe state: survives importlib.reload()
_STATE_KEY = '_autolineage_state'


def _get_state():
    if _STATE_KEY not in sys.modules:
        class _State:
            unified_tracker = None
            registry = None
            initialized = False
        sys.modules[_STATE_KEY] = _State()
    return sys.modules[_STATE_KEY]


def start_tracking(db_path: str = 'lineage.db',
                   script_path: str = None) -> UnifiedTracker:
    state = _get_state()
    if state.initialized:
        return state.unified_tracker

    state.unified_tracker = UnifiedTracker()

    # Legacy tracker for backward compat
    try:
        from .tracker import DatasetTracker
        _lt = DatasetTracker(db_path)
        _lt.start_run(script_path)
        from .hooks_legacy import enable_hooks
        enable_hooks(_lt)
    except Exception:
        pass

    state.registry = HookRegistry()
    installed = state.registry.install_all(state.unified_tracker)

    total = sum(c for _, c in installed)
    if total > 0:
        print(f"AutoLineage: {total} hooks across {len(installed)} libraries")

    state.initialized = True
    return state.unified_tracker


def stop_tracking(status: str = 'completed') -> None:
    state = _get_state()
    if not state.initialized:
        return
    if state.registry:
        state.registry.uninstall_all()
        state.registry = None
    state.unified_tracker = None
    state.initialized = False


def get_tracker() -> Optional[UnifiedTracker]:
    return _get_state().unified_tracker


def get_summary():
    t = _get_state().unified_tracker
    return t.get_summary() if t else None


start_tracking()
atexit.register(lambda: stop_tracking() if _get_state().initialized else None)
