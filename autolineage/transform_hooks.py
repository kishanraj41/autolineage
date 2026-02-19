"""
Pandas DataFrame transformation hooks.

Hooks into DataFrame methods that transform data (dropna, merge, groupby,
fillna, rename, assign, query, etc.) to automatically track in-memory
lineage without any code changes from the user.

These hooks complement the I/O hooks in hooks.py. Together they give
complete lineage from file read → transformations → file write.
"""

import pandas as pd
from functools import wraps
from typing import Dict, Any, List, Optional

from .df_tracker import get_df_tracker

# Store original methods
_originals: Dict[str, Any] = {}


def _save(cls, name):
    """Save original method before monkey-patching."""
    key = f"{cls.__name__}.{name}"
    if key not in _originals:
        _originals[key] = getattr(cls, name)
    return _originals[key]


def _make_transform_hook(method_name, orig_fn, extract_params=None):
    """
    Factory: create a hooked version of a DataFrame method that records lineage.
    
    Args:
        method_name: Name of the method (e.g., "dropna")
        orig_fn: Original unpatched method
        extract_params: Optional callable(args, kwargs) -> dict of params to record
    """
    @wraps(orig_fn)
    def hooked(self, *args, **kwargs):
        result = orig_fn(self, *args, **kwargs)

        # Only track if result is a DataFrame or Series
        if isinstance(result, (pd.DataFrame, pd.Series)):
            tracker = get_df_tracker()
            params = {}
            if extract_params:
                try:
                    params = extract_params(args, kwargs)
                except Exception:
                    pass
            
            # For Series results from operations like groupby().sum(), 
            # wrap tracking but don't try to track columns
            if isinstance(result, pd.DataFrame):
                tracker.record_transformation(
                    operation=method_name,
                    parent_df=self,
                    result_df=result,
                    params=params
                )
            elif isinstance(result, pd.Series):
                # Convert to frame for tracking, but return original Series
                try:
                    as_frame = result.to_frame()
                    tracker.record_transformation(
                        operation=method_name,
                        parent_df=self if isinstance(self, pd.DataFrame) else None,
                        result_df=as_frame,
                        params=params
                    )
                except Exception:
                    pass

        return result
    return hooked


def _make_merge_hook(orig_fn):
    """Special hook for pd.merge / DataFrame.merge that tracks both inputs."""
    @wraps(orig_fn)
    def hooked(*args, **kwargs):
        # pd.merge(left, right, ...) or df.merge(right, ...)
        result = orig_fn(*args, **kwargs)

        if isinstance(result, pd.DataFrame):
            tracker = get_df_tracker()

            # Figure out left and right DataFrames
            left = args[0] if len(args) > 0 else kwargs.get('left')
            right = args[1] if len(args) > 1 else kwargs.get('right')

            params = {}
            if 'on' in kwargs:
                params['on'] = kwargs['on'] if isinstance(kwargs['on'], str) else list(kwargs['on']) if kwargs['on'] else None
            if 'how' in kwargs:
                params['how'] = kwargs['how']
            if 'left_on' in kwargs:
                params['left_on'] = kwargs['left_on']
            if 'right_on' in kwargs:
                params['right_on'] = kwargs['right_on']

            extra_parents = [right] if isinstance(right, pd.DataFrame) else []
            tracker.record_transformation(
                operation="merge",
                parent_df=left if isinstance(left, pd.DataFrame) else None,
                result_df=result,
                params=params,
                extra_parents=extra_parents
            )

        return result
    return hooked


def _make_concat_hook(orig_fn):
    """Special hook for pd.concat that tracks all input DataFrames."""
    @wraps(orig_fn)
    def hooked(objs, *args, **kwargs):
        result = orig_fn(objs, *args, **kwargs)

        if isinstance(result, pd.DataFrame):
            tracker = get_df_tracker()
            
            df_list = [o for o in objs if isinstance(o, pd.DataFrame)]
            parent = df_list[0] if df_list else None
            extra = df_list[1:] if len(df_list) > 1 else []

            params = {}
            if 'axis' in kwargs:
                params['axis'] = kwargs['axis']
            if 'join' in kwargs:
                params['join'] = kwargs['join']
            params['n_inputs'] = len(df_list)

            tracker.record_transformation(
                operation="concat",
                parent_df=parent,
                result_df=result,
                params=params,
                extra_parents=extra
            )

        return result
    return hooked


def _make_groupby_hook(orig_fn):
    """
    Hook for DataFrame.groupby that returns a tracked GroupBy object.
    
    We can't directly hook the GroupBy result, but we can wrap the
    aggregation methods (sum, mean, count, agg, apply, etc.) on it.
    """
    @wraps(orig_fn)
    def hooked(self, *args, **kwargs):
        result = orig_fn(self, *args, **kwargs)

        # Attach the source DataFrame reference so aggregation hooks can use it
        result._lineage_source_df = self
        result._lineage_groupby_keys = args[0] if args else kwargs.get('by', [])

        return result
    return hooked


def _make_groupby_agg_hook(method_name, orig_fn):
    """Hook for GroupBy aggregation methods (sum, mean, count, etc.)."""
    @wraps(orig_fn)
    def hooked(self, *args, **kwargs):
        result = orig_fn(self, *args, **kwargs)

        if isinstance(result, (pd.DataFrame, pd.Series)):
            tracker = get_df_tracker()
            source_df = getattr(self, '_lineage_source_df', None)
            group_keys = getattr(self, '_lineage_groupby_keys', [])

            params = {'groupby_keys': group_keys if isinstance(group_keys, list) else [group_keys]}
            
            result_df = result if isinstance(result, pd.DataFrame) else result.to_frame()
            
            tracker.record_transformation(
                operation=f"groupby.{method_name}",
                parent_df=source_df,
                result_df=result_df,
                params=params
            )

        return result
    return hooked


def _make_getitem_hook(orig_fn):
    """Hook for DataFrame.__getitem__ (column selection / filtering)."""
    @wraps(orig_fn)
    def hooked(self, key):
        result = orig_fn(self, key)
        
        tracker = get_df_tracker()
        
        # Only track meaningful selections (not single column access which is very frequent)
        if isinstance(key, list) and isinstance(result, pd.DataFrame):
            # Multi-column selection: df[['a', 'b']]
            tracker.record_transformation(
                operation="select_columns",
                parent_df=self,
                result_df=result,
                params={'columns': key}
            )
        elif isinstance(key, pd.Series) and key.dtype == bool:
            # Boolean indexing: df[df['age'] > 30]
            if isinstance(result, pd.DataFrame):
                tracker.record_transformation(
                    operation="filter",
                    parent_df=self,
                    result_df=result,
                    params={'type': 'boolean_mask', 'rows_selected': int(key.sum())}
                )

        return result
    return hooked


# ============================================================
# HOOK INSTALLATION
# ============================================================

# DataFrame methods to hook: method_name -> param_extractor
_TRANSFORM_METHODS = {
    'dropna': lambda a, kw: {
        'axis': kw.get('axis', 0),
        'how': kw.get('how', 'any'),
        'subset': kw.get('subset'),
    },
    'fillna': lambda a, kw: {
        'value': str(a[0])[:100] if a else str(kw.get('value', ''))[:100],
        'method': kw.get('method'),
    },
    'drop': lambda a, kw: {
        'labels': kw.get('labels') or (list(a[0]) if a and hasattr(a[0], '__iter__') else (a[0] if a else None)),
        'axis': kw.get('axis', 0),
    },
    'drop_duplicates': lambda a, kw: {
        'subset': kw.get('subset'),
        'keep': kw.get('keep', 'first'),
    },
    'rename': lambda a, kw: {
        'columns': kw.get('columns'),
        'mapper': str(kw.get('mapper'))[:100] if kw.get('mapper') else None,
    },
    'astype': lambda a, kw: {
        'dtype': str(a[0])[:200] if a else str(kw.get('dtype'))[:200],
    },
    'sort_values': lambda a, kw: {
        'by': a[0] if a else kw.get('by'),
        'ascending': kw.get('ascending', True),
    },
    'reset_index': lambda a, kw: {
        'drop': kw.get('drop', False),
    },
    'set_index': lambda a, kw: {
        'keys': a[0] if a else kw.get('keys'),
    },
    'query': lambda a, kw: {
        'expr': a[0] if a else kw.get('expr'),
    },
    'assign': lambda a, kw: {
        'new_columns': list(kw.keys()),
    },
    'pivot_table': lambda a, kw: {
        'values': kw.get('values'),
        'index': kw.get('index'),
        'columns': kw.get('columns'),
        'aggfunc': str(kw.get('aggfunc', 'mean')),
    },
    'melt': lambda a, kw: {
        'id_vars': kw.get('id_vars'),
        'value_vars': kw.get('value_vars'),
    },
    'explode': lambda a, kw: {
        'column': a[0] if a else kw.get('column'),
    },
    'apply': lambda a, kw: {
        'func': str(a[0].__name__) if a and callable(a[0]) else str(a[0])[:100] if a else 'unknown',
        'axis': kw.get('axis', 0),
    },
    'replace': lambda a, kw: {
        'to_replace': str(a[0])[:100] if a else str(kw.get('to_replace'))[:100],
    },
    'clip': lambda a, kw: {
        'lower': kw.get('lower'),
        'upper': kw.get('upper'),
    },
    'sample': lambda a, kw: {
        'n': kw.get('n'),
        'frac': kw.get('frac'),
        'random_state': kw.get('random_state'),
    },
    'head': lambda a, kw: {
        'n': a[0] if a else kw.get('n', 5),
    },
    'tail': lambda a, kw: {
        'n': a[0] if a else kw.get('n', 5),
    },
    'nlargest': lambda a, kw: {
        'n': a[0] if a else kw.get('n'),
        'columns': a[1] if len(a) > 1 else kw.get('columns'),
    },
    'nsmallest': lambda a, kw: {
        'n': a[0] if a else kw.get('n'),
        'columns': a[1] if len(a) > 1 else kw.get('columns'),
    },
}

# GroupBy aggregation methods to hook
_GROUPBY_AGG_METHODS = [
    'sum', 'mean', 'median', 'std', 'var', 'min', 'max',
    'count', 'first', 'last', 'agg', 'aggregate', 'apply', 'transform',
]


def install_transform_hooks():
    """Install all in-memory transformation hooks."""
    count = 0

    # 1. DataFrame transformation methods
    for method_name, param_extractor in _TRANSFORM_METHODS.items():
        if hasattr(pd.DataFrame, method_name):
            orig = _save(pd.DataFrame, method_name)
            setattr(
                pd.DataFrame,
                method_name,
                _make_transform_hook(method_name, orig, param_extractor)
            )
            count += 1

    # 2. DataFrame.merge (instance method)
    if hasattr(pd.DataFrame, 'merge'):
        orig_merge = _save(pd.DataFrame, 'merge')
        pd.DataFrame.merge = _make_merge_hook(orig_merge)
        count += 1

    # 3. pd.merge (module-level function)
    _originals['pd.merge'] = pd.merge
    pd.merge = _make_merge_hook(pd.merge)
    count += 1

    # 4. pd.concat
    _originals['pd.concat'] = pd.concat
    pd.concat = _make_concat_hook(pd.concat)
    count += 1

    # 5. DataFrame.groupby
    orig_groupby = _save(pd.DataFrame, 'groupby')
    pd.DataFrame.groupby = _make_groupby_hook(orig_groupby)
    count += 1

    # 6. GroupBy aggregation methods
    from pandas.core.groupby import DataFrameGroupBy, SeriesGroupBy
    for agg_method in _GROUPBY_AGG_METHODS:
        for cls in [DataFrameGroupBy, SeriesGroupBy]:
            if hasattr(cls, agg_method):
                key = f"{cls.__name__}.{agg_method}"
                if key not in _originals:
                    _originals[key] = getattr(cls, agg_method)
                setattr(cls, agg_method, _make_groupby_agg_hook(agg_method, _originals[key]))
                count += 1

    # 7. DataFrame.__getitem__ (column selection and boolean filtering)
    orig_getitem = _save(pd.DataFrame, '__getitem__')
    pd.DataFrame.__getitem__ = _make_getitem_hook(orig_getitem)
    count += 1

    return count


def uninstall_transform_hooks():
    """Restore all original methods."""
    for key, orig in _originals.items():
        parts = key.split('.')
        if key == 'pd.merge':
            pd.merge = orig
        elif key == 'pd.concat':
            pd.concat = orig
        elif len(parts) == 2:
            cls_name, method_name = parts
            # Resolve class
            if cls_name == 'DataFrame':
                setattr(pd.DataFrame, method_name, orig)
            elif cls_name == 'DataFrameGroupBy':
                from pandas.core.groupby import DataFrameGroupBy
                setattr(DataFrameGroupBy, method_name, orig)
            elif cls_name == 'SeriesGroupBy':
                from pandas.core.groupby import SeriesGroupBy
                setattr(SeriesGroupBy, method_name, orig)
    _originals.clear()
