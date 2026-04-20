"""Pandas DataFrame transformation hook provider. 30+ methods."""

from functools import wraps
from typing import Dict, Any, Callable, Optional
from . import BaseHookProvider

_TRANSFORM_METHODS: Dict[str, Optional[Callable]] = {
    'dropna': lambda a, kw: {'axis': kw.get('axis', 0), 'how': kw.get('how', 'any'), 'subset': kw.get('subset')},
    'fillna': lambda a, kw: {'value': str(a[0])[:100] if a else str(kw.get('value', ''))[:100]},
    'drop': lambda a, kw: {'labels': kw.get('labels') or (list(a[0]) if a and hasattr(a[0], '__iter__') else (a[0] if a else None)), 'axis': kw.get('axis', 0)},
    'drop_duplicates': lambda a, kw: {'subset': kw.get('subset'), 'keep': kw.get('keep', 'first')},
    'rename': lambda a, kw: {'columns': kw.get('columns')},
    'astype': lambda a, kw: {'dtype': str(a[0])[:200] if a else str(kw.get('dtype'))[:200]},
    'sort_values': lambda a, kw: {'by': a[0] if a else kw.get('by')},
    'reset_index': lambda a, kw: {'drop': kw.get('drop', False)},
    'set_index': lambda a, kw: {'keys': a[0] if a else kw.get('keys')},
    'query': lambda a, kw: {'expr': a[0] if a else kw.get('expr')},
    'assign': lambda a, kw: {'new_columns': list(kw.keys())},
    'pivot_table': lambda a, kw: {'values': kw.get('values'), 'index': kw.get('index'), 'columns': kw.get('columns')},
    'melt': lambda a, kw: {'id_vars': kw.get('id_vars'), 'value_vars': kw.get('value_vars')},
    'explode': lambda a, kw: {'column': a[0] if a else kw.get('column')},
    'clip': lambda a, kw: {'lower': kw.get('lower'), 'upper': kw.get('upper')},
    'replace': lambda a, kw: {'to_replace': str(a[0])[:100] if a else str(kw.get('to_replace'))[:100]},
    'apply': lambda a, kw: {'func': getattr(a[0], '__name__', str(a[0])[:80]) if a else 'unknown'},
    'sample': lambda a, kw: {'n': kw.get('n'), 'frac': kw.get('frac')},
    'head': lambda a, kw: {'n': a[0] if a else kw.get('n', 5)},
    'tail': lambda a, kw: {'n': a[0] if a else kw.get('n', 5)},
    'nlargest': lambda a, kw: {'n': a[0] if a else kw.get('n'), 'columns': a[1] if len(a) > 1 else kw.get('columns')},
}

_GROUPBY_AGG_METHODS = [
    'sum', 'mean', 'median', 'std', 'var', 'min', 'max',
    'count', 'first', 'last', 'agg', 'aggregate', 'apply', 'transform',
]


class PandasTransformHooks(BaseHookProvider):
    name = "pandas-transforms"
    required_package = "pandas"

    def __init__(self):
        super().__init__()
        # Depth counter to block nested pandas ops
        # (e.g. drop_duplicates calls __getitem__ internally)
        self._hook_depth = 0

    def install(self, tracker) -> int:
        import pandas as pd
        from pandas.core.groupby import DataFrameGroupBy, SeriesGroupBy
        self._tracker = tracker
        count = 0

        for method_name, param_extractor in _TRANSFORM_METHODS.items():
            if not hasattr(pd.DataFrame, method_name):
                continue
            orig = self._save_original(pd.DataFrame, method_name)
            setattr(pd.DataFrame, method_name, self._make_transform_hook(method_name, orig, param_extractor))
            count += 1

        if hasattr(pd.DataFrame, 'merge'):
            orig = self._save_original(pd.DataFrame, 'merge')
            setattr(pd.DataFrame, 'merge', self._make_merge_hook(orig))
            count += 1

        self._originals['pd.merge'] = pd.merge
        pd.merge = self._make_merge_hook(pd.merge)
        count += 1

        self._originals['pd.concat'] = pd.concat
        pd.concat = self._make_concat_hook(pd.concat)
        count += 1

        orig_gb = self._save_original(pd.DataFrame, 'groupby')
        setattr(pd.DataFrame, 'groupby', self._make_groupby_hook(orig_gb))
        count += 1

        for agg_method in _GROUPBY_AGG_METHODS:
            for cls in [DataFrameGroupBy, SeriesGroupBy]:
                if not hasattr(cls, agg_method):
                    continue
                key = f"{cls.__name__}.{agg_method}"
                if key not in self._originals:
                    self._originals[key] = getattr(cls, agg_method)
                setattr(cls, agg_method, self._make_groupby_agg_hook(agg_method, self._originals[key]))
                count += 1

        orig_gi = self._save_original(pd.DataFrame, '__getitem__')
        setattr(pd.DataFrame, '__getitem__', self._make_getitem_hook(orig_gi))
        count += 1

        return count

    def uninstall(self) -> None:
        import pandas as pd
        from pandas.core.groupby import DataFrameGroupBy, SeriesGroupBy

        for method_name in _TRANSFORM_METHODS:
            self._restore_original(pd.DataFrame, method_name)
        self._restore_original(pd.DataFrame, 'merge')
        self._restore_original(pd.DataFrame, 'groupby')
        self._restore_original(pd.DataFrame, '__getitem__')
        if 'pd.merge' in self._originals:
            pd.merge = self._originals['pd.merge']
        if 'pd.concat' in self._originals:
            pd.concat = self._originals['pd.concat']
        for agg_method in _GROUPBY_AGG_METHODS:
            for cls in [DataFrameGroupBy, SeriesGroupBy]:
                key = f"{cls.__name__}.{agg_method}"
                if key in self._originals:
                    setattr(cls, agg_method, self._originals[key])
        self._originals.clear()

    def _make_transform_hook(self, method_name, orig_fn, param_extractor):
        provider = self

        @wraps(orig_fn)
        def hooked(self_df, *args, **kwargs):
            if provider._hook_depth >= 1:
                return orig_fn(self_df, *args, **kwargs)
            provider._hook_depth += 1
            try:
                result, duration = provider._timed(orig_fn, self_df, *args, **kwargs)
            finally:
                provider._hook_depth -= 1
            import pandas as pd
            if isinstance(result, (pd.DataFrame, pd.Series)):
                target = result
                if isinstance(result, pd.Series):
                    try:
                        target = result.to_frame()
                    except Exception:
                        return result
                parent_lid = provider._get_or_assign(self_df, source="untracked")
                child_lid = provider._get_or_assign(target, source=method_name)
                params = {}
                if param_extractor:
                    try:
                        params = param_extractor(args, kwargs)
                    except Exception:
                        pass
                added, removed = provider._col_diff(
                    self_df.columns if hasattr(self_df, 'columns') else None,
                    target.columns if hasattr(target, 'columns') else None)
                rec = provider._make_record(
                    category="transform", operation=method_name,
                    parent_ids=[parent_lid], child_id=child_lid,
                    parameters=provider._safe_params(params),
                    input_shape=tuple(self_df.shape), output_shape=tuple(target.shape),
                    columns_added=added, columns_removed=removed,
                    rows_before=len(self_df), rows_after=len(target), duration_ms=duration)
                provider._emit(rec)
            return result
        return hooked

    def _make_merge_hook(self, orig_fn):
        provider = self

        @wraps(orig_fn)
        def hooked(*args, **kwargs):
            result, duration = provider._timed(orig_fn, *args, **kwargs)
            import pandas as pd
            if isinstance(result, pd.DataFrame):
                left = args[0] if len(args) > 0 else kwargs.get('left')
                right = args[1] if len(args) > 1 else kwargs.get('right')
                parent_ids = []
                if isinstance(left, pd.DataFrame):
                    parent_ids.append(provider._get_or_assign(left, source="untracked"))
                if isinstance(right, pd.DataFrame):
                    parent_ids.append(provider._get_or_assign(right, source="untracked"))
                child_lid = provider._get_or_assign(result, source="merge")
                params = {k: kwargs[k] for k in ('on', 'how', 'left_on', 'right_on') if k in kwargs}
                rec = provider._make_record(
                    category="transform", operation="merge",
                    parent_ids=parent_ids, child_id=child_lid,
                    parameters=provider._safe_params(params),
                    input_shape=tuple(left.shape) if hasattr(left, 'shape') else None,
                    output_shape=tuple(result.shape),
                    rows_before=len(left) if hasattr(left, '__len__') else None,
                    rows_after=len(result), duration_ms=duration)
                provider._emit(rec)
            return result
        return hooked

    def _make_concat_hook(self, orig_fn):
        provider = self

        @wraps(orig_fn)
        def hooked(objs, *args, **kwargs):
            result, duration = provider._timed(orig_fn, objs, *args, **kwargs)
            import pandas as pd
            if isinstance(result, pd.DataFrame):
                parent_ids = []
                for obj in objs:
                    if isinstance(obj, pd.DataFrame):
                        parent_ids.append(provider._get_or_assign(obj, source="untracked"))
                child_lid = provider._get_or_assign(result, source="concat")
                rec = provider._make_record(
                    category="transform", operation="concat",
                    parent_ids=parent_ids, child_id=child_lid,
                    parameters={'n_inputs': len(objs), 'axis': kwargs.get('axis', 0)},
                    output_shape=tuple(result.shape),
                    rows_after=len(result), duration_ms=duration)
                provider._emit(rec)
            return result
        return hooked

    def _make_groupby_hook(self, orig_fn):
        @wraps(orig_fn)
        def hooked(self_df, *args, **kwargs):
            result = orig_fn(self_df, *args, **kwargs)
            try:
                result._autolineage_parent = self_df
            except Exception:
                pass
            return result
        return hooked

    def _make_groupby_agg_hook(self, agg_name, orig_fn):
        provider = self

        @wraps(orig_fn)
        def hooked(self_gb, *args, **kwargs):
            result, duration = provider._timed(orig_fn, self_gb, *args, **kwargs)
            import pandas as pd
            target = result
            if isinstance(result, pd.Series):
                try:
                    target = result.to_frame()
                except Exception:
                    return result
            if isinstance(target, pd.DataFrame):
                parent_df = getattr(self_gb, '_autolineage_parent', None)
                parent_lid = ""
                if parent_df is not None:
                    parent_lid = provider._get_or_assign(parent_df, source="untracked")
                child_lid = provider._get_or_assign(target, source=f"groupby.{agg_name}")
                by_keys = getattr(self_gb, 'keys', None)
                rec = provider._make_record(
                    category="transform", operation=f"groupby.{agg_name}",
                    parent_ids=[parent_lid] if parent_lid else [],
                    child_id=child_lid,
                    parameters=provider._safe_params({'by': by_keys, 'agg': agg_name}),
                    input_shape=tuple(parent_df.shape) if parent_df is not None else None,
                    output_shape=tuple(target.shape),
                    rows_before=len(parent_df) if parent_df is not None else None,
                    rows_after=len(target), duration_ms=duration)
                provider._emit(rec)
            return result
        return hooked

    def _make_getitem_hook(self, orig_fn):
        provider = self

        @wraps(orig_fn)
        def hooked(self_df, key):
            if provider._hook_depth >= 1:
                return orig_fn(self_df, key)
            provider._hook_depth += 1
            try:
                result = orig_fn(self_df, key)
            finally:
                provider._hook_depth -= 1
            import pandas as pd
            if isinstance(result, pd.DataFrame):
                parent_lid = provider._get_or_assign(self_df, source="untracked")
                child_lid = provider._get_or_assign(result, source="select")
                added, removed = provider._col_diff(self_df.columns, result.columns)
                rec = provider._make_record(
                    category="transform",
                    operation="select" if isinstance(key, (list, pd.Index)) else "filter",
                    parent_ids=[parent_lid], child_id=child_lid,
                    input_shape=tuple(self_df.shape), output_shape=tuple(result.shape),
                    columns_added=added, columns_removed=removed,
                    rows_before=len(self_df), rows_after=len(result))
                provider._emit(rec)
            return result
        return hooked
