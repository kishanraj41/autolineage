"""Polars hook provider (skeleton)."""
from . import BaseHookProvider

class PolarsHooks(BaseHookProvider):
    name = "polars"
    required_package = "polars"
    def install(self, tracker) -> int:
        self._tracker = tracker
        return 0
    def uninstall(self) -> None:
        self._originals.clear()
