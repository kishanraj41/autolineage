"""Checks computed from a recorded run and a saved baseline.

Each check names the corpus incidents it comes from and reports the
caller's file and line. A violation is a divergence the check can see
in the trace. Declarations that are not row counts (cumulative columns,
keys, a date, a source column) live in a contract and are measured while
the run is recorded.
"""

from __future__ import annotations

import json
import os
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .core import TransformationRecord

# Absolute difference in row-change rate that counts as a different step.
ROW_RATE_TOLERANCE = 0.01
# Absolute increase in null fraction that counts as a new coerce loss.
NULL_RATE_TOLERANCE = 0.01
DEFAULT_VOLUME_BAND = 0.20

COERCE_OPERATIONS = frozenset({"to_datetime", "to_numeric", "astype"})

INCIDENT_REFS = {
    "row_conservation": ("SF-002", "SF-018", "SF-022"),
    "null_rate_after_coerce": ("SF-001", "SF-020", "SF-021"),
    "monotonic_cumulative": ("SF-016",),
    "unique_keys_timestamps": ("SF-024", "SF-025", "SF-028", "SF-029", "SF-031"),
    "freshness_and_volume": ("SF-019", "SF-036"),
}

_CONTRACT: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class Violation:
    """One failed check at one recorded call."""

    check: str
    incident_refs: Tuple[str, ...]
    operation: str
    source_file: Optional[str]
    source_line: Optional[int]
    message: str

    def format(self) -> str:
        """One line a CI log can point at."""
        place = self.operation
        if self.source_file and self.source_line:
            place = f"{self.source_file}:{self.source_line} {self.operation}"
        refs = ", ".join(self.incident_refs)
        return f"{self.check} {place} {self.message} [{refs}]"


def set_contract(contract: Optional[Dict[str, Any]]) -> None:
    """Install the declarations the hooks measure. ``None`` clears them."""
    global _CONTRACT
    _CONTRACT = contract


def get_contract() -> Optional[Dict[str, Any]]:
    """The contract installed for the current process, if any."""
    return _CONTRACT


def load_contract(path: str) -> Dict[str, Any]:
    """Read a contract JSON file."""
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"contract must be a JSON object: {path}")
    return data


def annotate_output(rec: TransformationRecord, obj: Any) -> None:
    """Attach check signals to ``rec`` from the frame the operation returned.

    Null fraction is recorded for type coercion. Cumulative columns, keys,
    dates and per-source counts are recorded only when a contract names them.
    Failures here never change the user's result.
    """
    try:
        _annotate(rec, obj)
    except Exception:
        return


def _annotate(rec: TransformationRecord, obj: Any) -> None:
    import pandas as pd

    if not isinstance(obj, (pd.DataFrame, pd.Series)):
        return
    meta = rec.metadata if isinstance(rec.metadata, dict) else {}
    rec.metadata = meta
    if rec.operation in COERCE_OPERATIONS:
        rate = _null_rate(obj)
        if rate is not None:
            meta["null_rate"] = rate
    contract = _CONTRACT or {}
    if not contract or not isinstance(obj, pd.DataFrame):
        return
    monotonic = {}
    for column in contract.get("cumulative") or []:
        series = _column_or_index(obj, column)
        if series is not None:
            monotonic[str(column)] = bool(series.is_monotonic_increasing)
    if monotonic:
        meta["monotonic"] = monotonic
    duplicates = {}
    names = list(contract.get("keys") or [])
    if contract.get("time_index"):
        names.append(contract["time_index"])
    for column in names:
        series = _column_or_index(obj, column)
        if series is not None:
            duplicates[str(column)] = int(series.duplicated().sum())
    if duplicates:
        meta["duplicate_counts"] = duplicates
    date_column = contract.get("date_column")
    if date_column:
        series = _column_or_index(obj, date_column)
        if series is not None:
            parsed = pd.to_datetime(series, errors="coerce")
            latest = parsed.max()
            if pd.notna(latest):
                meta["max_date"] = latest.isoformat()
    source_column = contract.get("source_column")
    if source_column and source_column in getattr(obj, "columns", []):
        counts = obj[source_column].astype(str).value_counts()
        meta["source_counts"] = {str(key): int(value) for key, value in counts.items()}


def _null_rate(obj: Any) -> Optional[float]:
    import pandas as pd

    if isinstance(obj, pd.Series):
        if len(obj) == 0:
            return 0.0
        return float(obj.isna().mean())
    if isinstance(obj, pd.DataFrame):
        if obj.size == 0:
            return 0.0
        return float(obj.isna().to_numpy().mean())
    return None


def _column_or_index(frame: Any, name: str):
    if name in frame.columns:
        return frame[name]
    index = frame.index
    if getattr(index, "name", None) == name:
        return index.to_series()
    return None


def save_run(path: str, records: Sequence[TransformationRecord],
             contract: Optional[Dict[str, Any]] = None) -> None:
    """Write a check baseline: the records plus the contract used to measure them."""
    payload = {
        "contract": contract or {},
        "records": [_jsonable_record(rec) for rec in records],
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def load_run(path: str) -> Tuple[List[TransformationRecord], Dict[str, Any]]:
    """Load a baseline written by :func:`save_run`."""
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    contract = payload.get("contract") or {}
    records = []
    for item in payload.get("records") or []:
        for key in ("input_shape", "output_shape"):
            if isinstance(item.get(key), list):
                item[key] = tuple(item[key])
        records.append(TransformationRecord(**item))
    return records, contract


def _jsonable_record(rec: TransformationRecord) -> Dict[str, Any]:
    item = rec.to_dict()
    for key in ("input_shape", "output_shape"):
        if isinstance(item.get(key), tuple):
            item[key] = list(item[key])
    return item


def capture_run(script: str, contract: Optional[Dict[str, Any]] = None
                ) -> Tuple[List[TransformationRecord], Optional[str]]:
    """Run ``script`` with tracking on. Returns records and an error string."""
    from .auto import get_tracker, start_tracking, stop_tracking

    import sys
    previous = os.environ.get("AUTOLINEAGE_QUIET")
    os.environ["AUTOLINEAGE_QUIET"] = "1"
    set_contract(contract)
    stop_tracking()
    start_tracking()
    error = None
    records: List[TransformationRecord] = []
    try:
        import runpy
        script_path = str(Path(script).resolve())
        sys.path.insert(0, str(Path(script_path).parent))
        mod_name = "_autolineage_check_target"
        sys.modules.pop(mod_name, None)
        try:
            runpy.run_path(script_path, run_name=mod_name)
        except SystemExit as exc:
            if exc.code not in (0, None):
                error = f"SystemExit {exc.code}"
        tracker = get_tracker()
        if tracker is not None:
            records = list(tracker.records)
    except Exception:
        error = traceback.format_exc(limit=8)
        records = []
    finally:
        set_contract(None)
        stop_tracking()
        sys.modules.pop("_autolineage_check_target", None)
        if previous is None:
            os.environ.pop("AUTOLINEAGE_QUIET", None)
        else:
            os.environ["AUTOLINEAGE_QUIET"] = previous
    return records, error


def evaluate(current: Sequence[TransformationRecord],
             baseline: Sequence[TransformationRecord],
             contract: Optional[Dict[str, Any]] = None) -> List[Violation]:
    """Run every check. Returns the violations, in check order."""
    contract = contract or {}
    found: List[Violation] = []
    found.extend(row_conservation(current, baseline))
    found.extend(null_rate_after_coerce(current, baseline))
    found.extend(monotonic_cumulative(current, contract))
    found.extend(unique_keys_timestamps(current, contract))
    found.extend(freshness_and_volume(current, baseline, contract))
    return found


def row_conservation(current: Sequence[TransformationRecord],
                     baseline: Sequence[TransformationRecord]) -> List[Violation]:
    """Row-change rate at a step diverged from the baseline step.

    Merge fan-out and a truncation or filter that was not in the baseline
    both show up here, because both change ``rows_after`` relative to
    ``rows_before``.
    """
    found = []
    partners = _partners(baseline)
    for key, rec in _by_occurrence(current):
        rate = _row_rate(rec)
        if rate is None:
            continue
        partner = partners.get(key)
        base_rate = _row_rate(partner) if partner is not None else None
        if base_rate is None:
            if abs(rate) <= ROW_RATE_TOLERANCE:
                continue
            expected = "no baseline step"
        elif abs(rate - base_rate) <= ROW_RATE_TOLERANCE:
            continue
        else:
            expected = _row_phrase(partner)
        found.append(_violation(
            "row_conservation", rec,
            f"rows { _row_phrase(rec) }, baseline {expected}",
        ))
    return found


def null_rate_after_coerce(current: Sequence[TransformationRecord],
                           baseline: Sequence[TransformationRecord]) -> List[Violation]:
    """Null fraction after ``to_datetime``, ``to_numeric`` or ``astype`` rose."""
    found = []
    partners = _partners(baseline)
    for key, rec in _by_occurrence(current):
        if rec.operation not in COERCE_OPERATIONS:
            continue
        rate = _meta_float(rec, "null_rate")
        if rate is None:
            continue
        partner = partners.get(key)
        base = _meta_float(partner, "null_rate") if partner is not None else 0.0
        if rate - base <= NULL_RATE_TOLERANCE:
            continue
        found.append(_violation(
            "null_rate_after_coerce", rec,
            f"null fraction {rate:.3f}, baseline {base:.3f}",
        ))
    return found


def monotonic_cumulative(current: Sequence[TransformationRecord],
                         contract: Dict[str, Any]) -> List[Violation]:
    """A declared cumulative column decreased."""
    declared = [str(name) for name in (contract.get("cumulative") or [])]
    if not declared:
        return []
    found = []
    for rec in current:
        flags = (rec.metadata or {}).get("monotonic") or {}
        for column in declared:
            if column in flags and not flags[column]:
                found.append(_violation(
                    "monotonic_cumulative", rec,
                    f"cumulative column {column} decreased",
                ))
    return found


def unique_keys_timestamps(current: Sequence[TransformationRecord],
                           contract: Dict[str, Any]) -> List[Violation]:
    """A declared key or time index was not unique."""
    names = [str(name) for name in (contract.get("keys") or [])]
    if contract.get("time_index"):
        names.append(str(contract["time_index"]))
    if not names:
        return []
    found = []
    for rec in current:
        counts = (rec.metadata or {}).get("duplicate_counts") or {}
        for column in names:
            extras = counts.get(column)
            if extras:
                found.append(_violation(
                    "unique_keys_timestamps", rec,
                    f"{column} has {extras} duplicate values",
                ))
    return found


def freshness_and_volume(current: Sequence[TransformationRecord],
                         baseline: Sequence[TransformationRecord],
                         contract: Dict[str, Any]) -> List[Violation]:
    """The latest date went backwards, or a source's row count left its band."""
    if not contract.get("date_column") and not contract.get("source_column"):
        return []
    found = []
    current_date = _latest_date(current)
    baseline_date = _latest_date(baseline)
    if current_date is not None and baseline_date is not None and current_date < baseline_date:
        rec = _record_with(current, "max_date")
        if rec is not None:
            found.append(_violation(
                "freshness_and_volume", rec,
                f"max date {current_date} is older than baseline {baseline_date}",
            ))
    band = float(contract.get("volume_band", DEFAULT_VOLUME_BAND))
    base_peaks = _source_peaks(baseline)
    cur_peaks = _source_peaks(current)
    rec = _record_with(current, "source_counts")
    for source, base_count in sorted(base_peaks.items()):
        current_count = cur_peaks.get(source, 0)
        if base_count == 0:
            continue
        if abs(current_count - base_count) / base_count <= band:
            continue
        if rec is None:
            continue
        found.append(_violation(
            "freshness_and_volume", rec,
            f"source {source} has {current_count} rows, baseline {base_count}",
        ))
    return found


def _violation(check: str, rec: TransformationRecord, message: str) -> Violation:
    meta = rec.metadata or {}
    line = meta.get("source_line")
    return Violation(
        check=check,
        incident_refs=INCIDENT_REFS[check],
        operation=rec.operation,
        source_file=meta.get("source_file"),
        source_line=int(line) if isinstance(line, int) else None,
        message=message,
    )


def _by_occurrence(records: Iterable[TransformationRecord]):
    counts: Dict[str, int] = {}
    paired = []
    for rec in records:
        index = counts.get(rec.operation, 0)
        counts[rec.operation] = index + 1
        paired.append((f"{rec.operation}:{index}", rec))
    return paired


def _partners(records: Sequence[TransformationRecord]) -> Dict[str, TransformationRecord]:
    return {key: rec for key, rec in _by_occurrence(records)}


def _row_rate(rec: Optional[TransformationRecord]) -> Optional[float]:
    if rec is None or rec.rows_before in (None, 0) or rec.rows_after is None:
        return None
    return (rec.rows_after - rec.rows_before) / rec.rows_before


def _row_phrase(rec: Optional[TransformationRecord]) -> str:
    if rec is None or rec.rows_before is None or rec.rows_after is None:
        return "unknown"
    return f"{rec.rows_before} -> {rec.rows_after}"


def _meta_float(rec: Optional[TransformationRecord], key: str) -> Optional[float]:
    if rec is None:
        return None
    value = (rec.metadata or {}).get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _latest_date(records: Sequence[TransformationRecord]) -> Optional[str]:
    found = [
        (rec.metadata or {}).get("max_date")
        for rec in records
        if (rec.metadata or {}).get("max_date")
    ]
    if not found:
        return None
    return max(str(value) for value in found)


def _source_peaks(records: Sequence[TransformationRecord]) -> Dict[str, int]:
    peaks: Dict[str, int] = {}
    for rec in records:
        for source, count in ((rec.metadata or {}).get("source_counts") or {}).items():
            peaks[str(source)] = max(peaks.get(str(source), 0), int(count))
    return peaks


def _record_with(records: Sequence[TransformationRecord], key: str
                 ) -> Optional[TransformationRecord]:
    match = None
    for rec in records:
        if (rec.metadata or {}).get(key):
            match = rec
    return match
