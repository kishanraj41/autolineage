"""
Hook registry. Discovers and installs all available hook providers.
"""

import importlib
from typing import List, Tuple, Optional

from ..core.tracker import UnifiedTracker
from . import BaseHookProvider

_PROVIDERS = [
    ("autolineage.hooks.pandas_io", "PandasIOHooks"),
    ("autolineage.hooks.pandas_transform", "PandasTransformHooks"),
    ("autolineage.hooks.numpy_hooks", "NumpyHooks"),
    ("autolineage.hooks.sklearn_hooks", "SklearnHooks"),
    ("autolineage.hooks.xgboost_hooks", "XGBoostHooks"),
    ("autolineage.hooks.lightgbm_hooks", "LightGBMHooks"),
    ("autolineage.hooks.pyspark_hooks", "PySparkHooks"),
    ("autolineage.hooks.polars_hooks", "PolarsHooks"),
]


class HookRegistry:
    _globally_installed: set = set()

    def __init__(self):
        self._installed: List[BaseHookProvider] = []

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

        return results

    def uninstall_all(self) -> None:
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

    @staticmethod
    def _load_provider(module_path, class_name) -> Optional[BaseHookProvider]:
        try:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            return cls()
        except (ImportError, AttributeError, Exception):
            return None
