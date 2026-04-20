"""XGBoost hook provider (skeleton)."""
from . import BaseHookProvider

class XGBoostHooks(BaseHookProvider):
    name = "xgboost"
    required_package = "xgboost"
    def install(self, tracker) -> int:
        self._tracker = tracker
        return 0
    def uninstall(self) -> None:
        self._originals.clear()
