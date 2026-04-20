"""LightGBM hook provider (skeleton)."""
from . import BaseHookProvider

class LightGBMHooks(BaseHookProvider):
    name = "lightgbm"
    required_package = "lightgbm"
    def install(self, tracker) -> int:
        self._tracker = tracker
        return 0
    def uninstall(self) -> None:
        self._originals.clear()
