"""Bring child-process records back to the parent tracker.

``RF.py`` runs its split, fit, predict, and metric lines inside
``multiprocess.Process``. A spawned child is a new interpreter, so the
parent's patches are not there, and a forked child keeps its records in
its own memory. Either way the lines were invisible.

After tracking is installed, ``multiprocessing.Process`` and
``multiprocess.Process`` run the user's target in a wrapper. The wrapper
installs the hooks, rebinds early imports in the modules the child has
loaded, and writes the new records to a file. ``join`` reads that file
into the parent tracker.
"""

import atexit
import os
import pickle
import tempfile
import threading
from functools import wraps

_QUIET = "AUTOLINEAGE_QUIET"
_LOCK = threading.Lock()
_TRACKER = None
_PATCHED = []
_PENDING = {}
_ATEXIT = False


def install_process_capture(tracker) -> None:
    """Record later child processes into ``tracker`` when they are joined."""
    global _TRACKER, _ATEXIT
    _TRACKER = tracker
    for mod_name in ("multiprocessing", "multiprocess"):
        try:
            mod = __import__(mod_name, fromlist=["Process"])
        except ImportError:
            continue
        process_cls = getattr(mod, "Process", None)
        if process_cls is not None:
            _patch(process_cls)
    if not _ATEXIT:
        atexit.register(_collect_pending)
        _ATEXIT = True


def uninstall_process_capture() -> None:
    """Restore ``Process`` and stop accepting child records."""
    global _TRACKER
    for cls, orig_init, orig_start, orig_join in _PATCHED:
        cls.__init__ = orig_init
        cls.start = orig_start
        cls.join = orig_join
    _PATCHED.clear()
    _TRACKER = None


def _patch(process_cls) -> None:
    if getattr(process_cls.__init__, "_autolineage_wrapped", False):
        return
    orig_init = process_cls.__init__
    orig_start = process_cls.start
    orig_join = process_cls.join

    @wraps(orig_init)
    def __init__(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        target = getattr(self, "_target", None)
        if target is None or getattr(target, "_autolineage_child", False):
            return
        fd, path = tempfile.mkstemp(prefix="al-proc-", suffix=".pkl")
        os.close(fd)
        self._al_path = path
        with _LOCK:
            _PENDING[path] = True
        self._target = _child_entry
        self._args = (
            target,
            getattr(self, "_args", ()),
            getattr(self, "_kwargs", {}) or {},
            path,
        )
        self._kwargs = {}

    __init__._autolineage_wrapped = True

    @wraps(orig_start)
    def start(self, *args, **kwargs):
        old = os.environ.get(_QUIET)
        os.environ[_QUIET] = "1"
        try:
            return orig_start(self, *args, **kwargs)
        finally:
            if old is None:
                os.environ.pop(_QUIET, None)
            else:
                os.environ[_QUIET] = old

    @wraps(orig_join)
    def join(self, timeout=None):
        result = orig_join(self, timeout)
        if getattr(self, "exitcode", None) is not None:
            _collect(getattr(self, "_al_path", None))
        return result

    process_cls.__init__ = __init__
    process_cls.start = start
    process_cls.join = join
    _PATCHED.append((process_cls, orig_init, orig_start, orig_join))


def _child_entry(target, args, kwargs, path):
    from autolineage.auto import _get_state, start_tracking

    tracker = start_tracking()
    registry = _get_state().registry
    if registry is not None:
        _rebind_loaded_user_modules(registry)
    before = len(tracker.records)
    try:
        return target(*args, **(kwargs or {}))
    finally:
        _write_records(path, tracker.records[before:])


_child_entry._autolineage_child = True


def _rebind_loaded_user_modules(registry) -> None:
    """Rebind early imports in every non-library module already loaded.

    A spawned child imports the script before this wrapper runs, so names
    such as ``train_test_split`` point at the unhooked functions. The
    script is not always ``__main__`` (pytest loads it as a test module;
    spawn also aliases ``__mp_main__``).
    """
    import sys

    from autolineage.hooks import _is_library_frame

    seen = set()
    for mod in list(sys.modules.values()):
        if mod is None or id(mod) in seen:
            continue
        seen.add(id(mod))
        filename = getattr(mod, "__file__", None)
        if not isinstance(filename, str):
            continue
        try:
            if _is_library_frame(filename):
                continue
        except Exception:
            continue
        registry.rebind_module(mod)


def _write_records(path, records) -> None:
    payload = []
    for rec in records:
        try:
            payload.append(rec.to_dict())
        except Exception:
            continue
    tmp = path + ".tmp"
    try:
        with open(tmp, "wb") as handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _collect(path) -> None:
    if not path:
        return
    with _LOCK:
        pending = path in _PENDING
        _PENDING.pop(path, None)
    if _TRACKER is None:
        return
    if not pending and not os.path.exists(path):
        return
    try:
        with open(path, "rb") as handle:
            payload = pickle.load(handle)
    except Exception:
        payload = []
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    if not isinstance(payload, list):
        return
    from autolineage.core import TransformationRecord

    for item in payload:
        if not isinstance(item, dict):
            continue
        for key in ("input_shape", "output_shape"):
            if isinstance(item.get(key), list):
                item[key] = tuple(item[key])
        try:
            _TRACKER.record(TransformationRecord(**item))
        except Exception:
            continue


def _collect_pending() -> None:
    with _LOCK:
        paths = list(_PENDING)
    for path in paths:
        _collect(path)
