"""
AutoLineage - Automatic ML Data Lineage Tracking

Track your data lineage automatically from raw data to trained models
without manual logging.
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

# Import main classes for easy access
from .database import LineageDatabase
from .tracker import DatasetTracker, hash_file, get_file_info
from .graph import LineageGraph
from .reporter import ComplianceReporter

# Define what's available when doing "from autolineage import *"
__all__ = [
    'LineageDatabase',
    'DatasetTracker',
    'LineageGraph',
    'ComplianceReporter',
    'hash_file',
    'get_file_info',
    '__version__',
]


def get_version():
    """Return the current version."""
    return __version__


# Package-level configuration
DEFAULT_DB_PATH = "lineage.db"


# Jupyter extension
def load_ipython_extension(ipython):
    """Load Jupyter magic commands."""
    from .magic import load_ipython_extension as load_magic
    load_magic(ipython)


def unload_ipython_extension(ipython):
    """Unload Jupyter magic commands."""
    from .magic import unload_ipython_extension as unload_magic
    unload_magic(ipython)