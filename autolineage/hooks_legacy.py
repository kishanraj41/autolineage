"""Legacy hooks module for backward compatibility."""

_tracker = None

def enable_hooks(tracker=None):
    global _tracker
    if tracker:
        _tracker = tracker
    return _tracker

def get_tracker():
    return _tracker
