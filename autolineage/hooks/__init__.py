"""
Base hook provider interface.

Every library plugin implements ``BaseHookProvider``.
"""

from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Dict, Any, Optional, Tuple
import json
import os
import sys
import time

from ..core.tracker import UnifiedTracker
from ..core import TransformationRecord

# Package directory, not the repo root: user scripts live next to the
# repo and must still be stamped with their own file and line.
_PKG_DIR = os.path.normcase(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
_STDLIB_DIR = os.path.normcase(os.path.abspath(os.path.dirname(os.__file__)))


def _source_stamp_enabled() -> bool:
    """False when ``AUTOLINEAGE_SOURCE_STAMP=0``.

    Stamping records the caller's file and line. Filter expressions also
    store a slice of the caller's source. Both stay off when this is set.
    """
    return os.environ.get("AUTOLINEAGE_SOURCE_STAMP", "1") != "0"


@lru_cache(maxsize=256)
def _is_library_frame(filename: str) -> bool:
    """True for frames that are not the caller's script or notebook."""
    if not filename or filename.startswith("<"):
        return not filename.startswith("<ipython-input")
    norm = os.path.normcase(os.path.abspath(filename))
    if norm.startswith(_PKG_DIR + os.sep):
        return True
    parts = set(norm.split(os.sep))
    if "site-packages" in parts or "dist-packages" in parts:
        return True
    if norm.startswith(_STDLIB_DIR + os.sep):
        return True
    return False


def _caller_source() -> Tuple[Optional[str], Optional[int]]:
    """First frame outside this package, the stdlib, and installed libraries."""
    frame = sys._getframe(0)
    while frame is not None:
        filename = frame.f_code.co_filename
        if not _is_library_frame(filename):
            return os.path.abspath(filename), frame.f_lineno
        frame = frame.f_back
    return None, None


def _stamp_source(rec: TransformationRecord) -> None:
    """Record the user line that issued this call, when one is on the stack."""
    if not _source_stamp_enabled():
        return
    meta = rec.metadata if isinstance(rec.metadata, dict) else {}
    if not isinstance(rec.metadata, dict):
        rec.metadata = meta
    if meta.get("source_file") and meta.get("source_line"):
        return
    filename, lineno = _caller_source()
    if filename is None:
        return
    meta.setdefault("source_file", filename)
    meta.setdefault("source_line", lineno)


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
            _stamp_source(rec)
            if not rec.content_hash and rec.child_id:
                node = self._tracker.nodes.get(rec.child_id)
                if node and node.get('content_hash'):
                    rec.content_hash = node['content_hash']
            self._tracker.record(rec)

    def _get_or_assign(self, obj, **kwargs) -> str:
        if self._tracker is None:
            return ""
        return self._tracker.get_or_assign(obj, **kwargs)

    def _assign_new(self, obj, **kwargs) -> str:
        """A fresh lineage id, overwriting one pandas copied from the parent."""
        if self._tracker is None:
            return ""
        return self._tracker.assign_id(obj, **kwargs)

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

    @staticmethod
    def _cols(obj):
        """Column names of a DataFrame-like object as strings, or None.

        Used to populate ``TransformationRecord.input_columns`` /
        ``output_columns`` so the analyzer can compare column *sets*
        between runs, not just column counts.
        """
        cols = getattr(obj, 'columns', None)
        if cols is None:
            return None
        try:
            return [str(c) for c in cols]
        except Exception:
            return None


# Backward compatibility
try:
    from ..hooks_legacy import enable_hooks, get_tracker
except (ImportError, SyntaxError):
    def enable_hooks(tracker=None):
        pass
    def get_tracker():
        return None
