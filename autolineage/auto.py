"""
Auto-tracking module. Import to enable automatic lineage tracking.

    import autolineage.auto

This is the recommended entry point for end users: it installs hooks
across every available framework before any user code runs, so that
subsequent ``from sklearn.metrics import f1_score`` statements bind
to the wrapped versions automatically.
"""

import atexit
import sys
from typing import Optional

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


def start_tracking() -> UnifiedTracker:
    """Idempotent: safe to call multiple times. Returns the global tracker."""
    state = _get_state()
    if state.initialized:
        return state.unified_tracker

    state.unified_tracker = UnifiedTracker()
    state.registry = HookRegistry()
    installed = state.registry.install_all(state.unified_tracker)

    total = sum(c for _, c in installed)
    if total > 0:
        active = [n for n, c in installed if c > 0]
        print(f"AutoLineage: {total} hooks installed across {len(active)} "
              f"frameworks ({', '.join(active)})")

    state.initialized = True
    return state.unified_tracker


def stop_tracking() -> None:
    state = _get_state()
    if not state.initialized:
        return
    if state.registry:
        state.registry.uninstall_all()
        state.registry = None
    state.unified_tracker = None
    state.initialized = False


def get_tracker() -> Optional[UnifiedTracker]:
    """Return the global tracker, or None if tracking is not active."""
    return _get_state().unified_tracker


def get_summary():
    t = _get_state().unified_tracker
    return t.get_summary() if t else None


def visualize(output: Optional[str] = None, *, inline: bool = False,
              open_browser: bool = True):
    """Convenience wrapper: visualize the global tracker's lineage."""
    t = get_tracker()
    if t is None:
        raise RuntimeError(
            "Tracking not active. Did 'import autolineage.auto' run?")
    return t.visualize(output=output, inline=inline, open_browser=open_browser)


# Auto-start on import; clean up on interpreter exit.
start_tracking()
atexit.register(lambda: stop_tracking() if _get_state().initialized else None)
