"""
Auto-tracking module.

Simply import this module to enable automatic lineage tracking:

    import autolineage.auto

Or with custom configuration:

    from autolineage.auto import start_tracking
    tracker = start_tracking(db_path='my_lineage.db')
"""

from .tracker import DatasetTracker
from .hooks import enable_hooks, get_tracker


# Global tracker instance
_auto_tracker = None


def start_tracking(db_path='lineage.db', script_path=None):
    """
    Start automatic tracking.
    
    Args:
        db_path: Path to SQLite database
        script_path: Path to script being tracked
        
    Returns:
        DatasetTracker instance
    """
    global _auto_tracker
    
    if _auto_tracker is not None:
        print("⚠ Tracking already started")
        return _auto_tracker
    
    # Create tracker
    _auto_tracker = DatasetTracker(db_path)
    _auto_tracker.start_run(script_path)
    
    # Enable hooks
    enable_hooks(_auto_tracker)
    
    return _auto_tracker


def stop_tracking(status='completed'):
    """
    Stop automatic tracking.
    
    Args:
        status: Run status (completed, failed, etc.)
    """
    global _auto_tracker
    
    if _auto_tracker is None:
        print("⚠ No active tracking to stop")
        return
    
    _auto_tracker.end_run(status)
    _auto_tracker.close()
    _auto_tracker = None
    
    print("✓ Tracking stopped")


def get_summary():
    """Get lineage summary for current tracking session."""
    if _auto_tracker is None:
        print("⚠ No active tracking session")
        return None
    
    return _auto_tracker.get_lineage_summary()


# Auto-start tracking when module is imported
print("AutoLineage: Starting automatic tracking...")
start_tracking()

# Register cleanup on exit
import atexit
atexit.register(lambda: stop_tracking() if _auto_tracker else None)