"""
Function hooks for automatic lineage tracking.
Intercepts pandas, numpy, and scikit-learn functions.
"""

import pandas as pd
import numpy as np
from functools import wraps
import inspect
import os
from typing import Callable, Any

# Global tracker instance (will be set when hooks are enabled)
_tracker = None


def set_tracker(tracker):
    """Set the global tracker instance."""
    global _tracker
    _tracker = tracker


def get_tracker():
    """Get the global tracker instance."""
    return _tracker


# Store original functions before we replace them
_original_functions = {}


def save_original(module, func_name):
    """Save original function before replacing."""
    key = f"{module.__name__}.{func_name}"
    if key not in _original_functions:
        _original_functions[key] = getattr(module, func_name)
    return _original_functions[key]


def get_original(module, func_name):
    """Get saved original function."""
    key = f"{module.__name__}.{func_name}"
    return _original_functions.get(key)


# ============================================================
# PANDAS HOOKS
# ============================================================

def hook_pandas():
    """Hook into pandas I/O functions."""
    
    # Save originals
    _orig_read_csv = save_original(pd, 'read_csv')
    _orig_read_parquet = save_original(pd, 'read_parquet')
    _orig_read_json = save_original(pd, 'read_json')
    _orig_read_excel = save_original(pd, 'read_excel')
    _orig_read_pickle = save_original(pd, 'read_pickle')
    
    _orig_to_csv = save_original(pd.DataFrame, 'to_csv')
    _orig_to_parquet = save_original(pd.DataFrame, 'to_parquet')
    _orig_to_json = save_original(pd.DataFrame, 'to_json')
    _orig_to_excel = save_original(pd.DataFrame, 'to_excel')
    _orig_to_pickle = save_original(pd.DataFrame, 'to_pickle')
    
    # ===== READ FUNCTIONS =====
    
    @wraps(_orig_read_csv)
    def tracked_read_csv(filepath_or_buffer, *args, **kwargs):
        """Tracked version of pd.read_csv"""
        # Call original function
        result = _orig_read_csv(filepath_or_buffer, *args, **kwargs)
        
        # Track if tracker is available and filepath is a string
        if _tracker and isinstance(filepath_or_buffer, str):
            if os.path.exists(filepath_or_buffer):
                _tracker.track_file(filepath_or_buffer, 'read')
        
        return result
    
    @wraps(_orig_read_parquet)
    def tracked_read_parquet(path, *args, **kwargs):
        """Tracked version of pd.read_parquet"""
        result = _orig_read_parquet(path, *args, **kwargs)
        
        if _tracker and isinstance(path, str):
            if os.path.exists(path):
                _tracker.track_file(path, 'read')
        
        return result
    
    @wraps(_orig_read_json)
    def tracked_read_json(path_or_buf, *args, **kwargs):
        """Tracked version of pd.read_json"""
        result = _orig_read_json(path_or_buf, *args, **kwargs)
        
        if _tracker and isinstance(path_or_buf, str):
            if os.path.exists(path_or_buf):
                _tracker.track_file(path_or_buf, 'read')
        
        return result
    
    @wraps(_orig_read_excel)
    def tracked_read_excel(io, *args, **kwargs):
        """Tracked version of pd.read_excel"""
        result = _orig_read_excel(io, *args, **kwargs)
        
        if _tracker and isinstance(io, str):
            if os.path.exists(io):
                _tracker.track_file(io, 'read')
        
        return result
    
    @wraps(_orig_read_pickle)
    def tracked_read_pickle(filepath_or_buffer, *args, **kwargs):
        """Tracked version of pd.read_pickle"""
        result = _orig_read_pickle(filepath_or_buffer, *args, **kwargs)
        
        if _tracker and isinstance(filepath_or_buffer, str):
            if os.path.exists(filepath_or_buffer):
                _tracker.track_file(filepath_or_buffer, 'read')
        
        return result
    
    # ===== WRITE FUNCTIONS =====
    
    @wraps(_orig_to_csv)
    def tracked_to_csv(self, path_or_buf=None, *args, **kwargs):
        """Tracked version of DataFrame.to_csv"""
        # Call original
        result = _orig_to_csv(self, path_or_buf, *args, **kwargs)
        
        # Track if tracker is available and path is a string
        if _tracker and path_or_buf and isinstance(path_or_buf, str):
            _tracker.track_file(path_or_buf, 'write')
        
        return result
    
    @wraps(_orig_to_parquet)
    def tracked_to_parquet(self, path, *args, **kwargs):
        """Tracked version of DataFrame.to_parquet"""
        result = _orig_to_parquet(self, path, *args, **kwargs)
        
        if _tracker and isinstance(path, str):
            _tracker.track_file(path, 'write')
        
        return result
    
    @wraps(_orig_to_json)
    def tracked_to_json(self, path_or_buf=None, *args, **kwargs):
        """Tracked version of DataFrame.to_json"""
        result = _orig_to_json(self, path_or_buf, *args, **kwargs)
        
        if _tracker and path_or_buf and isinstance(path_or_buf, str):
            _tracker.track_file(path_or_buf, 'write')
        
        return result
    
    @wraps(_orig_to_excel)
    def tracked_to_excel(self, excel_writer, *args, **kwargs):
        """Tracked version of DataFrame.to_excel"""
        result = _orig_to_excel(self, excel_writer, *args, **kwargs)
        
        if _tracker and isinstance(excel_writer, str):
            _tracker.track_file(excel_writer, 'write')
        
        return result
    
    @wraps(_orig_to_pickle)
    def tracked_to_pickle(self, path, *args, **kwargs):
        """Tracked version of DataFrame.to_pickle"""
        result = _orig_to_pickle(self, path, *args, **kwargs)
        
        if _tracker and isinstance(path, str):
            _tracker.track_file(path, 'write')
        
        return result
    
    # Replace pandas functions with tracked versions
    pd.read_csv = tracked_read_csv
    pd.read_parquet = tracked_read_parquet
    pd.read_json = tracked_read_json
    pd.read_excel = tracked_read_excel
    pd.read_pickle = tracked_read_pickle
    
    pd.DataFrame.to_csv = tracked_to_csv
    pd.DataFrame.to_parquet = tracked_to_parquet
    pd.DataFrame.to_json = tracked_to_json
    pd.DataFrame.to_excel = tracked_to_excel
    pd.DataFrame.to_pickle = tracked_to_pickle
    
    print("✓ Pandas hooks installed")


# ============================================================
# NUMPY HOOKS
# ============================================================

def hook_numpy():
    """Hook into numpy I/O functions."""
    
    # Save originals
    _orig_load = save_original(np, 'load')
    _orig_save = save_original(np, 'save')
    _orig_loadtxt = save_original(np, 'loadtxt')
    _orig_savetxt = save_original(np, 'savetxt')
    
    @wraps(_orig_load)
    def tracked_load(file, *args, **kwargs):
        """Tracked version of np.load"""
        result = _orig_load(file, *args, **kwargs)
        
        if _tracker and isinstance(file, str):
            if os.path.exists(file):
                _tracker.track_file(file, 'read')
        
        return result
    
    @wraps(_orig_save)
    def tracked_save(file, arr, *args, **kwargs):
        """Tracked version of np.save"""
        result = _orig_save(file, arr, *args, **kwargs)
        
        if _tracker and isinstance(file, str):
            # np.save adds .npy extension automatically
            filepath = file if file.endswith('.npy') else f"{file}.npy"
            _tracker.track_file(filepath, 'write')
        
        return result
    
    @wraps(_orig_loadtxt)
    def tracked_loadtxt(fname, *args, **kwargs):
        """Tracked version of np.loadtxt"""
        result = _orig_loadtxt(fname, *args, **kwargs)
        
        if _tracker and isinstance(fname, str):
            if os.path.exists(fname):
                _tracker.track_file(fname, 'read')
        
        return result
    
    @wraps(_orig_savetxt)
    def tracked_savetxt(fname, X, *args, **kwargs):
        """Tracked version of np.savetxt"""
        result = _orig_savetxt(fname, X, *args, **kwargs)
        
        if _tracker and isinstance(fname, str):
            _tracker.track_file(fname, 'write')
        
        return result
    
    # Replace numpy functions
    np.load = tracked_load
    np.save = tracked_save
    np.loadtxt = tracked_loadtxt
    np.savetxt = tracked_savetxt
    
    print("✓ NumPy hooks installed")


# ============================================================
# SCIKIT-LEARN HOOKS (Model Persistence)
# ============================================================

def hook_sklearn():
    """Hook into scikit-learn model persistence."""
    
    try:
        import joblib
        
        _orig_dump = save_original(joblib, 'dump')
        _orig_load = save_original(joblib, 'load')
        
        @wraps(_orig_dump)
        def tracked_dump(value, filename, *args, **kwargs):
            """Tracked version of joblib.dump"""
            result = _orig_dump(value, filename, *args, **kwargs)
            
            if _tracker and isinstance(filename, str):
                _tracker.track_file(filename, 'write')
            
            return result
        
        @wraps(_orig_load)
        def tracked_load(filename, *args, **kwargs):
            """Tracked version of joblib.load"""
            result = _orig_load(filename, *args, **kwargs)
            
            if _tracker and isinstance(filename, str):
                if os.path.exists(filename):
                    _tracker.track_file(filename, 'read')
            
            return result
        
        joblib.dump = tracked_dump
        joblib.load = tracked_load
        
        print("✓ Joblib hooks installed")
        
    except ImportError:
        print("⚠ Joblib not installed, skipping sklearn hooks")


# ============================================================
# PICKLE HOOKS
# ============================================================

def hook_pickle():
    """Hook into Python's pickle module."""
    
    import pickle
    
    _orig_dump = save_original(pickle, 'dump')
    _orig_load = save_original(pickle, 'load')
    
    @wraps(_orig_dump)
    def tracked_dump(obj, file, *args, **kwargs):
        """Tracked version of pickle.dump"""
        result = _orig_dump(obj, file, *args, **kwargs)
        
        # Track if file has a name attribute (file object)
        if _tracker and hasattr(file, 'name'):
            _tracker.track_file(file.name, 'write')
        
        return result
    
    @wraps(_orig_load)
    def tracked_load(file, *args, **kwargs):
        """Tracked version of pickle.load"""
        result = _orig_load(file, *args, **kwargs)
        
        if _tracker and hasattr(file, 'name'):
            _tracker.track_file(file.name, 'read')
        
        return result
    
    pickle.dump = tracked_dump
    pickle.load = tracked_load
    
    print("✓ Pickle hooks installed")


# ============================================================
# ENABLE/DISABLE ALL HOOKS
# ============================================================

def enable_hooks(tracker=None):
    """
    Enable all hooks for automatic tracking.
    
    Args:
        tracker: DatasetTracker instance. If None, creates a new one.
    """
    global _tracker
    
    if tracker:
        _tracker = tracker
    else:
        from .tracker import DatasetTracker
        _tracker = DatasetTracker()
        _tracker.start_run()
    
    print("\n" + "="*60)
    print("AUTOLINEAGE: Enabling automatic tracking")
    print("="*60)
    
    hook_pandas()
    hook_numpy()
    hook_sklearn()
    hook_pickle()
    
    print("="*60)
    print("✅ All hooks enabled! Tracking is now automatic.")
    print("="*60 + "\n")
    
    return _tracker


def disable_hooks():
    """Restore original functions."""
    
    print("\n" + "="*60)
    print("AUTOLINEAGE: Disabling hooks")
    print("="*60)
    
    # Restore pandas
    if 'pandas.read_csv' in _original_functions:
        pd.read_csv = _original_functions['pandas.read_csv']
        pd.read_parquet = _original_functions['pandas.read_parquet']
        pd.read_json = _original_functions['pandas.read_json']
        pd.read_excel = _original_functions['pandas.read_excel']
        pd.read_pickle = _original_functions['pandas.read_pickle']
        
        pd.DataFrame.to_csv = _original_functions['pandas.core.frame.DataFrame.to_csv']
        pd.DataFrame.to_parquet = _original_functions['pandas.core.frame.DataFrame.to_parquet']
        pd.DataFrame.to_json = _original_functions['pandas.core.frame.DataFrame.to_json']
        pd.DataFrame.to_excel = _original_functions['pandas.core.frame.DataFrame.to_excel']
        pd.DataFrame.to_pickle = _original_functions['pandas.core.frame.DataFrame.to_pickle']
        
        print("✓ Pandas hooks removed")
    
    # Restore numpy
    if 'numpy.load' in _original_functions:
        np.load = _original_functions['numpy.load']
        np.save = _original_functions['numpy.save']
        np.loadtxt = _original_functions['numpy.loadtxt']
        np.savetxt = _original_functions['numpy.savetxt']
        
        print("✓ NumPy hooks removed")
    
    # Restore joblib
    try:
        import joblib
        if 'joblib.dump' in _original_functions:
            joblib.dump = _original_functions['joblib.dump']
            joblib.load = _original_functions['joblib.load']
            print("✓ Joblib hooks removed")
    except ImportError:
        pass
    
    # Restore pickle
    import pickle
    if 'pickle.dump' in _original_functions:
        pickle.dump = _original_functions['pickle.dump']
        pickle.load = _original_functions['pickle.load']
        print("✓ Pickle hooks removed")
    
    print("="*60)
    print("✅ All hooks disabled")
    print("="*60 + "\n")