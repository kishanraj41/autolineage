"""
Hook registry. Discovers and installs all available hook providers.
"""

import importlib
import os
import sys
import warnings
from typing import Any, Dict, List, Tuple, Optional

from ..core.tracker import UnifiedTracker
from . import BaseHookProvider

_PROVIDERS = [
    ("autolineage.hooks.pandas_io", "PandasIOHooks"),
    ("autolineage.hooks.pandas_transform", "PandasTransformHooks"),
    ("autolineage.hooks.sklearn_hooks", "SklearnHooks"),
    ("autolineage.hooks.pyspark_hooks", "PySparkHooks"),
]

# Set to 0 / false / no to keep early-imported names untouched (warn only).
REBIND_ENV_VAR = "AUTOLINEAGE_REBIND_EARLY_IMPORTS"

# Short module aliases some providers use as _originals keys.
_KEY_ALIASES = {"pd": "pandas"}


class HookRegistry:
    _globally_installed: set = set()

    def __init__(self):
        self._installed: List[BaseHookProvider] = []
        # (namespace, name, original, replacement) for every early-bound
        # name this registry rebound, so uninstall_all() can undo it.
        self._rebound: List[Tuple[Any, str, Any, Any]] = []

    def install_all(self, tracker: UnifiedTracker) -> List[Tuple[str, int]]:
        """Install hooks for every available library. Safe to call multiple times."""
        results: List[Tuple[str, int]] = []

        for module_path, class_name in _PROVIDERS:
            provider_key = f"{module_path}.{class_name}"
            if provider_key in HookRegistry._globally_installed:
                continue

            provider = self._load_provider(module_path, class_name)
            if provider is None or not provider.is_available():
                continue

            try:
                count = provider.install(tracker)
                self._installed.append(provider)
                HookRegistry._globally_installed.add(provider_key)
                results.append((provider.name, count))
            except Exception as exc:
                pass  # silently skip failed providers

        if self._installed:
            self._handle_early_imports()
        return results

    def uninstall_all(self) -> None:
        self._restore_rebound()
        for provider in reversed(self._installed):
            try:
                provider.uninstall()
                # Remove from global set so re-install is possible
                for mp, cn in _PROVIDERS:
                    if cn == type(provider).__name__:
                        HookRegistry._globally_installed.discard(f"{mp}.{cn}")
            except Exception:
                pass
        self._installed.clear()

    @property
    def installed_providers(self) -> List[str]:
        return [p.name for p in self._installed]

    # ------------------------------------------------------------------
    # Early-bound imports
    # ------------------------------------------------------------------

    @staticmethod
    def _rebind_enabled() -> bool:
        return os.environ.get(REBIND_ENV_VAR, "1").strip().lower() not in ("0", "false", "no", "off")

    def _hooked_functions(self) -> Dict[int, Tuple[Any, Any, str]]:
        """Map id(original) -> (original, hooked replacement, public name)
        for every module-level function the installed providers patched.

        Class methods (``DataFrame.dropna`` etc.) are patched on the class,
        so references to them are looked up at call time and never go
        stale; only module attributes can be bound early by a
        ``from module import name`` and need this treatment.
        """
        found: Dict[int, Tuple[Any, Any, str]] = {}
        for provider in self._installed:
            for key, orig in list(getattr(provider, "_originals", {}).items()):
                owner_path, _, name = key.rpartition(".")
                if not owner_path or not callable(orig):
                    continue
                owner_path = _KEY_ALIASES.get(owner_path, owner_path)
                module = sys.modules.get(owner_path)
                if module is None:
                    try:
                        module = importlib.import_module(owner_path)
                    except Exception:
                        continue  # not a module (a class key) or unimportable
                current = getattr(module, name, None)
                if current is None or current is orig:
                    continue
                if getattr(current, "__wrapped__", None) is not orig:
                    continue  # replaced by something other than our hook
                found[id(orig)] = (orig, current, f"{owner_path}.{name}")
        return found

    def _handle_early_imports(self) -> None:
        """Find patched functions that ``__main__`` imported before the hooks
        were installed (``from sklearn.metrics import f1_score`` at the top
        of a script or notebook) and rebind those names to the tracked
        versions, so the calls are recorded instead of silently bypassing
        lineage. Emits a warning listing what happened either way.
        """
        main = sys.modules.get("__main__")
        if main is None:
            return
        hooked = self._hooked_functions()
        if not hooked:
            return

        rebind = self._rebind_enabled()
        leaked: List[Tuple[str, str]] = []
        for attr, val in list(vars(main).items()):
            if attr.startswith("_"):
                continue
            entry = hooked.get(id(val))
            if entry is None or val is not entry[0]:
                continue
            orig, replacement, public = entry
            leaked.append((attr, public))
            if rebind:
                setattr(main, attr, replacement)
                self._rebound.append((main, attr, orig, replacement))

        if not leaked:
            return
        names = ", ".join(f"{local} (= {public})" for local, public in sorted(leaked))
        if rebind:
            warnings.warn(
                f"AutoLineage: {names} imported BEFORE install_all(); rebound in "
                f"__main__ to the tracked versions, so these calls are now recorded. "
                f"Put 'import autolineage.auto' first to avoid this, or set "
                f"{REBIND_ENV_VAR}=0 to leave early imports untouched.",
                stacklevel=3,
            )
        else:
            warnings.warn(
                f"AutoLineage: {names} imported BEFORE install_all() and will not "
                f"be tracked ({REBIND_ENV_VAR}=0). Move the import after the "
                f"autolineage hook installation, or put 'import autolineage.auto' "
                f"at the very top of your script.",
                stacklevel=3,
            )

    def _restore_rebound(self) -> None:
        """Undo rebinding, but never clobber a name the user reassigned."""
        for namespace, attr, orig, replacement in reversed(self._rebound):
            try:
                if getattr(namespace, attr, None) is replacement:
                    setattr(namespace, attr, orig)
            except Exception:
                pass
        self._rebound.clear()

    @staticmethod
    def _load_provider(module_path, class_name) -> Optional[BaseHookProvider]:
        try:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            return cls()
        except (ImportError, AttributeError, Exception):
            return None
