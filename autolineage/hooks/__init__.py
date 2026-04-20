"""
Base hook provider interface.

Every library plugin implements ``BaseHookProvider``.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json
import time

from ..core.tracker import UnifiedTracker
from ..core import TransformationRecord


class BaseHookProvider(ABC):

    def __init__(self):
        self._tracker: Optional[UnifiedTracker] = None
        self._originals: Dict[str, Any] = {}

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable library name."""

    @property
    @abstractmethod
    def required_package(self) -> str:
        """Top-level import name for availability check."""

    @abstractmethod
    def install(self, tracker: UnifiedTracker) -> int:
        """Install hooks. Returns count of methods hooked."""

    @abstractmethod
    def uninstall(self) -> None:
        """Restore all original methods."""

    def is_available(self) -> bool:
        try:
            __import__(self.required_package)
            return True
        except ImportError:
            return False

    def _save_original(self, obj: Any, attr_name: str) -> Any:
        key = f"{self._qualified_name(obj)}.{attr_name}"
        if key not in self._originals:
            self._originals[key] = getattr(obj, attr_name)
        return self._originals[key]

    def _restore_original(self, obj: Any, attr_name: str) -> None:
        key = f"{self._qualified_name(obj)}.{attr_name}"
        if key in self._originals:
            setattr(obj, attr_name, self._originals[key])

    def _make_record(self, **kwargs) -> TransformationRecord:
        kwargs.setdefault('library', self.name)
        return TransformationRecord(**kwargs)

    def _emit(self, rec: TransformationRecord) -> None:
        """Send a record to the shared tracker. Auto-fills content_hash."""
        if self._tracker is not None:
            if not rec.content_hash and rec.child_id:
                node = self._tracker.nodes.get(rec.child_id)
                if node and node.get('content_hash'):
                    rec.content_hash = node['content_hash']
            self._tracker.record(rec)

    def _get_or_assign(self, obj, **kwargs) -> str:
        if self._tracker is None:
            return ""
        return self._tracker.get_or_assign(obj, **kwargs)

    def _get_id(self, obj) -> Optional[str]:
        if self._tracker is None:
            return None
        return self._tracker.get_id(obj)

    @staticmethod
    def _qualified_name(obj) -> str:
        if hasattr(obj, '__module__') and hasattr(obj, '__qualname__'):
            return f"{obj.__module__}.{obj.__qualname__}"
        if hasattr(obj, '__name__'):
            return obj.__name__
        return type(obj).__name__

    @staticmethod
    def _timed(fn, *args, **kwargs):
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        duration_ms = (time.perf_counter() - t0) * 1000
        return result, duration_ms

    @staticmethod
    def _safe_params(params: Dict) -> Dict:
        safe = {}
        for k, v in params.items():
            if v is None:
                safe[k] = None
                continue
            try:
                json.dumps(v)
                safe[k] = v
            except (TypeError, ValueError):
                safe[k] = str(v)[:200]
        return safe

    @staticmethod
    def _col_diff(parent_cols, child_cols):
        if parent_cols is None or child_cols is None:
            return None, None
        p = set(str(c) for c in parent_cols)
        c = set(str(c) for c in child_cols)
        added = sorted(c - p) or None
        removed = sorted(p - c) or None
        return added, removed


# Backward compatibility
try:
    from ..hooks_legacy import enable_hooks, get_tracker
except (ImportError, SyntaxError):
    def enable_hooks(tracker=None):
        pass
    def get_tracker():
        return None
