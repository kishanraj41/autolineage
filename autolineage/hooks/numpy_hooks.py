"""NumPy hook provider (skeleton)."""
from . import BaseHookProvider

class NumpyHooks(BaseHookProvider):
    name = "numpy"
    required_package = "numpy"
    def install(self, tracker) -> int:
        self._tracker = tracker
        return 0
    def uninstall(self) -> None:
        self._originals.clear()
