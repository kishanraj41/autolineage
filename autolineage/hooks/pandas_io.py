"""Pandas I/O hook provider."""

import os
from functools import wraps
from . import BaseHookProvider


def _path_str(value):
    """Filesystem path for a str or ``os.PathLike`` (including ``pathlib.Path``)."""
    if isinstance(value, (str, os.PathLike)):
        try:
            text = os.fspath(value)
        except TypeError:
            return None
        if isinstance(text, str):
            return text
    return None


class PandasIOHooks(BaseHookProvider):
    name = "pandas-io"
    required_package = "pandas"

    _READ_FUNCS = ['read_csv', 'read_parquet', 'read_json', 'read_excel', 'read_pickle']
    _WRITE_METHODS = ['to_csv', 'to_parquet', 'to_json', 'to_excel', 'to_pickle']

    def install(self, tracker) -> int:
        import pandas as pd
        self._tracker = tracker
        count = 0

        for fn_name in self._READ_FUNCS:
            if not hasattr(pd, fn_name):
                continue
            orig = self._save_original(pd, fn_name)
            setattr(pd, fn_name, self._make_read_hook(fn_name, orig))
            count += 1

        for fn_name in self._WRITE_METHODS:
            if not hasattr(pd.DataFrame, fn_name):
                continue
            orig = self._save_original(pd.DataFrame, fn_name)
            setattr(pd.DataFrame, fn_name, self._make_write_hook(fn_name, orig))
            count += 1

        return count

    def uninstall(self) -> None:
        import pandas as pd
        for fn_name in self._READ_FUNCS:
            self._restore_original(pd, fn_name)
        for fn_name in self._WRITE_METHODS:
            self._restore_original(pd.DataFrame, fn_name)
        self._originals.clear()

    def _make_read_hook(self, fn_name, orig_fn):
        provider = self

        @wraps(orig_fn)
        def hooked(filepath_or_buffer, *args, **kwargs):
            result, duration = provider._timed(orig_fn, filepath_or_buffer, *args, **kwargs)
            path = _path_str(filepath_or_buffer)
            if path and os.path.exists(path):
                abs_path = os.path.abspath(path)
                lid = provider._get_or_assign(result, source=fn_name, filepath=abs_path)
                rec = provider._make_record(
                    category="io", operation=fn_name,
                    parent_ids=[], child_id=lid,
                    output_shape=tuple(result.shape),
                    output_columns=list(result.columns) if hasattr(result, 'columns') else None,
                    rows_after=len(result), duration_ms=duration,
                    metadata={'filepath': abs_path},
                )
                provider._emit(rec)
            return result
        return hooked

    def _make_write_hook(self, fn_name, orig_fn):
        provider = self

        @wraps(orig_fn)
        def hooked(self_df, *args, **kwargs):
            result, duration = provider._timed(orig_fn, self_df, *args, **kwargs)

            # Extract path from positional or keyword args. pandas accepts
            # pathlib.Path anywhere it accepts a string.
            path = None
            if args:
                path = _path_str(args[0])
            if path is None:
                for key in ('path_or_buf', 'path', 'excel_writer', 'fname'):
                    if key in kwargs:
                        path = _path_str(kwargs[key])
                        if path:
                            break

            if path:
                parent_lid = provider._get_or_assign(self_df, source="untracked")
                rec = provider._make_record(
                    category="io", operation=fn_name,
                    parent_ids=[parent_lid], child_id="",
                    input_shape=tuple(self_df.shape),
                    rows_before=len(self_df), duration_ms=duration,
                    metadata={'filepath': os.path.abspath(path)},
                )
                provider._emit(rec)
            return result
        return hooked
