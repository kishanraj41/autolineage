"""PySpark hook provider. Transforms, I/O, groupBy, join, actions."""

from functools import wraps
from . import BaseHookProvider

_TRANSFORM_METHODS = [
    'filter', 'where', 'select', 'withColumn', 'withColumnRenamed',
    'drop', 'dropna', 'fillna', 'dropDuplicates', 'distinct',
    'orderBy', 'sort', 'limit', 'sample', 'coalesce', 'repartition',
]
_UNION_METHODS = ['union', 'unionAll', 'unionByName']
_GROUPBY_AGG_METHODS = ['agg', 'avg', 'count', 'max', 'mean', 'min', 'sum', 'pivot']
_READER_METHODS = ['csv', 'parquet', 'json', 'orc', 'table', 'load']
_WRITER_METHODS = ['csv', 'parquet', 'json', 'orc', 'save', 'saveAsTable']
_ACTION_METHODS = ['collect', 'count', 'show', 'take', 'head', 'first', 'toPandas']


class PySparkHooks(BaseHookProvider):
    name = "pyspark"
    required_package = "pyspark"

    def __init__(self):
        super().__init__()
        self._in_hook = False

    def _resolve_classes(self):
        from pyspark.sql import DataFrame, DataFrameReader, DataFrameWriter
        actual_df = DataFrame
        try:
            from pyspark.sql.classic.dataframe import DataFrame as ClassicDF
            actual_df = ClassicDF
        except ImportError:
            pass
        try:
            from pyspark.sql.classic.group import GroupedData
        except ImportError:
            from pyspark.sql import GroupedData
        actual_reader = DataFrameReader
        try:
            from pyspark.sql.classic.readwriter import DataFrameReader as CR
            actual_reader = CR
        except ImportError:
            pass
        actual_writer = DataFrameWriter
        try:
            from pyspark.sql.classic.readwriter import DataFrameWriter as CW
            actual_writer = CW
        except ImportError:
            pass
        return actual_df, actual_reader, actual_writer, GroupedData

    def install(self, tracker) -> int:
        self._tracker = tracker
        self._df_cls, self._reader_cls, self._writer_cls, self._gd_cls = self._resolve_classes()
        count = 0
        DF = self._df_cls

        for m in _TRANSFORM_METHODS:
            if hasattr(DF, m):
                orig = self._save_original(DF, m)
                setattr(DF, m, self._make_hook(m, orig, 'transform'))
                count += 1
        for m in _UNION_METHODS:
            if hasattr(DF, m):
                orig = self._save_original(DF, m)
                setattr(DF, m, self._make_two_input_hook(m, orig))
                count += 1
        for m in ['join', 'crossJoin']:
            if hasattr(DF, m):
                orig = self._save_original(DF, m)
                setattr(DF, m, self._make_two_input_hook(m, orig))
                count += 1
        if hasattr(DF, 'groupBy'):
            orig_gb = self._save_original(DF, 'groupBy')
            provider = self
            @wraps(orig_gb)
            def hooked_gb(self_df, *cols):
                result = orig_gb(self_df, *cols)
                try:
                    result._autolineage_parent = self_df
                    result._autolineage_keys = [str(c) for c in cols]
                except Exception:
                    pass
                return result
            DF.groupBy = hooked_gb
            if hasattr(DF, 'groupby'):
                DF.groupby = hooked_gb
            count += 1
        GD = self._gd_cls
        for m in _GROUPBY_AGG_METHODS:
            if hasattr(GD, m):
                orig = self._save_original(GD, m)
                setattr(GD, m, self._make_gd_hook(m, orig))
                count += 1
        Reader = self._reader_cls
        for m in _READER_METHODS:
            if hasattr(Reader, m):
                orig = self._save_original(Reader, m)
                setattr(Reader, m, self._make_reader_hook(m, orig))
                count += 1
        Writer = self._writer_cls
        for m in _WRITER_METHODS:
            if hasattr(Writer, m):
                orig = self._save_original(Writer, m)
                setattr(Writer, m, self._make_writer_hook(m, orig))
                count += 1
        for m in _ACTION_METHODS:
            if hasattr(DF, m):
                orig = self._save_original(DF, m)
                setattr(DF, m, self._make_action_hook(m, orig))
                count += 1
        return count

    def uninstall(self) -> None:
        DF, GD = self._df_cls, self._gd_cls
        for m in _TRANSFORM_METHODS + _UNION_METHODS + ['join', 'crossJoin'] + _ACTION_METHODS:
            self._restore_original(DF, m)
        self._restore_original(DF, 'groupBy')
        for m in _GROUPBY_AGG_METHODS:
            self._restore_original(GD, m)
        for m in _READER_METHODS:
            self._restore_original(self._reader_cls, m)
        for m in _WRITER_METHODS:
            self._restore_original(self._writer_cls, m)
        self._originals.clear()

    @staticmethod
    def _df_info(df):
        try:
            cols = df.columns if hasattr(df, 'columns') else []
            return {'columns': cols, 'n_cols': len(cols)}
        except Exception:
            return {'columns': [], 'n_cols': 0}

    def _make_hook(self, method_name, orig_fn, category):
        provider = self

        @wraps(orig_fn)
        def hooked(self_df, *args, **kwargs):
            if provider._in_hook:
                return orig_fn(self_df, *args, **kwargs)
            provider._in_hook = True
            try:
                result, duration = provider._timed(orig_fn, self_df, *args, **kwargs)
            finally:
                provider._in_hook = False
            from pyspark.sql import DataFrame as DF
            if isinstance(result, DF):
                parent_lid = provider._get_or_assign(self_df, source="spark_df")
                child_lid = provider._get_or_assign(result, source=method_name)
                pi, ci = provider._df_info(self_df), provider._df_info(result)
                added, removed = provider._col_diff(pi['columns'], ci['columns'])
                rec = provider._make_record(
                    category=category, operation=method_name,
                    parent_ids=[parent_lid], child_id=child_lid,
                    input_shape=(None, pi['n_cols']), output_shape=(None, ci['n_cols']),
                    output_columns=ci['columns'], columns_added=added,
                    columns_removed=removed, duration_ms=duration)
                provider._emit(rec)
            return result
        return hooked

    def _make_two_input_hook(self, method_name, orig_fn):
        provider = self

        @wraps(orig_fn)
        def hooked(self_df, other, *args, **kwargs):
            if provider._in_hook:
                return orig_fn(self_df, other, *args, **kwargs)
            provider._in_hook = True
            try:
                result, duration = provider._timed(orig_fn, self_df, other, *args, **kwargs)
            finally:
                provider._in_hook = False
            from pyspark.sql import DataFrame as DF
            if isinstance(result, DF):
                left_lid = provider._get_or_assign(self_df, source=f"{method_name}_left")
                right_lid = provider._get_or_assign(other, source=f"{method_name}_right")
                child_lid = provider._get_or_assign(result, source=method_name)
                ci = provider._df_info(result)
                rec = provider._make_record(
                    category="transform", operation=method_name,
                    parent_ids=[left_lid, right_lid], child_id=child_lid,
                    output_shape=(None, ci['n_cols']), output_columns=ci['columns'],
                    duration_ms=duration)
                provider._emit(rec)
            return result
        return hooked

    def _make_gd_hook(self, agg_name, orig_fn):
        provider = self

        @wraps(orig_fn)
        def hooked(self_gd, *args, **kwargs):
            if provider._in_hook:
                return orig_fn(self_gd, *args, **kwargs)
            provider._in_hook = True
            try:
                result, duration = provider._timed(orig_fn, self_gd, *args, **kwargs)
            finally:
                provider._in_hook = False
            from pyspark.sql import DataFrame as DF
            if isinstance(result, DF):
                parent_df = getattr(self_gd, '_autolineage_parent', None)
                parent_lid = provider._get_or_assign(parent_df, source="groupby_input") if parent_df else ""
                child_lid = provider._get_or_assign(result, source=f"groupBy.{agg_name}")
                ci = provider._df_info(result)
                rec = provider._make_record(
                    category="transform", operation=f"groupBy.{agg_name}",
                    parent_ids=[parent_lid] if parent_lid else [],
                    child_id=child_lid, output_shape=(None, ci['n_cols']),
                    output_columns=ci['columns'], duration_ms=duration)
                provider._emit(rec)
            return result
        return hooked

    def _make_reader_hook(self, method_name, orig_fn):
        provider = self

        @wraps(orig_fn)
        def hooked(self_reader, *args, **kwargs):
            if provider._in_hook:
                return orig_fn(self_reader, *args, **kwargs)
            provider._in_hook = True
            try:
                result, duration = provider._timed(orig_fn, self_reader, *args, **kwargs)
            finally:
                provider._in_hook = False
            from pyspark.sql import DataFrame as DF
            if isinstance(result, DF):
                path = str(args[0]) if args else None
                child_lid = provider._get_or_assign(result, source=method_name, filepath=path)
                ci = provider._df_info(result)
                rec = provider._make_record(
                    category="io", operation=f"read.{method_name}",
                    parent_ids=[], child_id=child_lid,
                    output_shape=(None, ci['n_cols']), output_columns=ci['columns'],
                    duration_ms=duration, metadata={'path': path})
                provider._emit(rec)
            return result
        return hooked

    def _make_writer_hook(self, method_name, orig_fn):
        provider = self

        @wraps(orig_fn)
        def hooked(self_writer, *args, **kwargs):
            if provider._in_hook:
                return orig_fn(self_writer, *args, **kwargs)
            provider._in_hook = True
            try:
                result, duration = provider._timed(orig_fn, self_writer, *args, **kwargs)
            finally:
                provider._in_hook = False
            source_df = getattr(self_writer, '_df', None)
            parent_lid = provider._get_or_assign(source_df, source="write_input") if source_df else ""
            path = str(args[0]) if args else ""
            rec = provider._make_record(
                category="io", operation=f"write.{method_name}",
                parent_ids=[parent_lid] if parent_lid else [],
                child_id="", duration_ms=duration, metadata={'path': path})
            provider._emit(rec)
            return result
        return hooked

    def _make_action_hook(self, method_name, orig_fn):
        provider = self

        @wraps(orig_fn)
        def hooked(self_df, *args, **kwargs):
            if provider._in_hook:
                return orig_fn(self_df, *args, **kwargs)
            provider._in_hook = True
            try:
                result, duration = provider._timed(orig_fn, self_df, *args, **kwargs)
            finally:
                provider._in_hook = False
            parent_lid = provider._get_or_assign(self_df, source="action_input")
            row_count = result if method_name == 'count' and isinstance(result, int) else None
            di = provider._df_info(self_df)
            rec = provider._make_record(
                category="action", operation=method_name,
                parent_ids=[parent_lid], child_id="",
                input_shape=(row_count, di['n_cols']), input_columns=di['columns'],
                rows_before=row_count, duration_ms=duration,
                metadata={'action': method_name, 'row_count': row_count})
            provider._emit(rec)
            return result
        return hooked
