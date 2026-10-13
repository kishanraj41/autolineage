"""
Lineage Analyzer: Anomaly Detection and Root Cause Localization.

Primary research contribution. Actively DETECTS when a pipeline's
behavior deviates from baseline and LOCALIZES which transformation
caused the problem. No existing tool does this on ML pipeline lineage.
"""

import difflib
import json
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple

from . import TransformationRecord


def _occurrence_keys(ops: List[str]) -> List[str]:
    """``op:n`` keys in sequence order. ``n`` counts that operation only."""
    counts: Dict[str, int] = {}
    keys = []
    for op in ops:
        counts[op] = counts.get(op, 0) + 1
        keys.append(f"{op}:{counts[op]}")
    return keys


def _partner_keys(bl_ops: List[str], cur_ops: List[str],
                  bl_deltas: Dict[str, int], cur_deltas: Dict[str, int]) -> Dict[str, Optional[str]]:
    """Map each current ``op:n`` key to the baseline key it continues, or None.

    ``SequenceMatcher`` aligns the operation names. An extra filter is then
    the same name as one already in the baseline, so a matched pair of the
    same name is swapped when an unmatched neighbour is closer in row delta.
    An empty baseline sequence keeps the old same-key pairing: fingerprints
    saved before ``operation_sequence`` existed still compare.
    """
    cur_keys = _occurrence_keys(cur_ops)
    if not bl_ops:
        return {key: key for key in cur_keys}
    bl_keys = _occurrence_keys(bl_ops)
    matcher = difflib.SequenceMatcher(a=bl_ops, b=cur_ops, autojunk=False)
    cur_to_bl = {index: None for index in range(len(cur_ops))}
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            continue
        for offset, current_index in enumerate(range(j1, j2)):
            cur_to_bl[current_index] = i1 + offset

    for _ in range(len(cur_ops) + 1):
        swapped = False
        for current_index, baseline_index in list(cur_to_bl.items()):
            if baseline_index is None:
                continue
            baseline_delta = bl_deltas.get(bl_keys[baseline_index])
            current_delta = cur_deltas.get(cur_keys[current_index])
            if baseline_delta is None or current_delta is None:
                continue
            for other_index, other_baseline in list(cur_to_bl.items()):
                if other_baseline is not None or cur_ops[other_index] != cur_ops[current_index]:
                    continue
                other_delta = cur_deltas.get(cur_keys[other_index])
                if other_delta is None:
                    continue
                if abs(other_delta - baseline_delta) + 1e-9 < abs(current_delta - baseline_delta):
                    cur_to_bl[other_index] = baseline_index
                    cur_to_bl[current_index] = None
                    swapped = True
                    break
            if swapped:
                break
        if not swapped:
            break

    return {
        cur_keys[index]: (None if baseline_index is None else bl_keys[baseline_index])
        for index, baseline_index in cur_to_bl.items()
    }


def _ranking_from_scores(tracker, scores) -> List[Dict[str, Any]]:
    """Attach the recorded caller line to each scored operation."""
    ranking = []
    for idx, score, op, evidence in scores:
        rec = tracker.records[idx]
        meta = rec.metadata if isinstance(rec.metadata, dict) else {}
        ranking.append({
            "step_index": idx,
            "operation": op,
            "score": min(float(score), 1.0),
            "source_file": meta.get("source_file"),
            "source_line": meta.get("source_line"),
            "evidence": evidence,
        })
    return ranking


@dataclass
class Anomaly:
    """A detected deviation from expected pipeline behavior."""
    severity: str
    operation: str
    step_index: int
    metric: str
    expected: Any
    actual: Any
    deviation: float
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RootCause:
    """Identified root cause of a metric degradation."""
    metric_name: str
    metric_baseline: float
    metric_actual: float
    root_operation: str
    root_step_index: int
    impact_score: float
    explanation: str
    evidence: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunFingerprint:
    """Compact summary of a pipeline run for comparison.

    Column-set fields (all keyed by ``operation:occurrence`` except
    ``columns_seen``) let the analyzer name the specific columns that
    appeared or disappeared between runs and attribute them to the
    operation where that happened, which column counts alone cannot do:

    * ``output_columns`` -- columns each operation produced
    * ``columns_added`` / ``columns_removed`` -- columns each operation
      created or dropped relative to its input
    * ``columns_seen`` -- every column name that appeared in any
      operation's input or output during the run

    Fingerprints written by older versions lack these fields and the
    membership checks become no-ops.
    """
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    total_records: int = 0
    operation_sequence: List[str] = field(default_factory=list)
    row_deltas: Dict[str, int] = field(default_factory=dict)
    col_counts: Dict[str, int] = field(default_factory=dict)
    durations: Dict[str, float] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    shapes: Dict[str, Any] = field(default_factory=dict)
    output_columns: Dict[str, List[str]] = field(default_factory=dict)
    columns_added: Dict[str, List[str]] = field(default_factory=dict)
    columns_removed: Dict[str, List[str]] = field(default_factory=dict)
    columns_seen: List[str] = field(default_factory=list)
    # Rows entering each operation. Together with ``row_deltas`` this is the
    # row-change *rate*, so a split that stays at 20% is not a suspect just
    # because the table going into it got smaller. Older fingerprints omit it.
    rows_before: Dict[str, int] = field(default_factory=dict)
    # Every value of a metric, in call order. ``metrics`` keeps the last
    # value so existing callers keep working.
    metric_runs: Dict[str, List[float]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> 'RunFingerprint':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def has_column_sets(self) -> bool:
        return bool(self.output_columns) and bool(self.columns_seen)

    def keys_in_order(self) -> List[str]:
        """``operation:occurrence`` keys in execution order."""
        occurrence: Dict[str, int] = {}
        keys = []
        for op in self.operation_sequence:
            occurrence[op] = occurrence.get(op, 0) + 1
            keys.append(f"{op}:{occurrence[op]}")
        return keys


class LineageAnalyzer:
    """Analyzes lineage records to detect anomalies and localize root causes.

    Usage::

        analyzer = LineageAnalyzer(tracker)
        anomalies = analyzer.detect_anomalies()
        cause = analyzer.localize_root_cause("accuracy")
        analyzer.save_fingerprint("fingerprints.json")
    """

    DEFAULT_THRESHOLDS = {
        'row_delta_pct': 20.0,
        'col_count_change': 0,
        'new_operation': True,
        'missing_operation': True,
        'metric_drop_pct': 5.0,
        'duration_spike_pct': 200.0,
        'column_membership': True,
    }

    # Column lists are not stored for frames wider than this; the
    # membership checks then skip that operation rather than bloating
    # the fingerprint file.
    MAX_TRACKED_COLUMNS = 5000

    # Localization weight for an operation that is the *origin* of a
    # column-set change (first appearance of a column the baseline never
    # produced, or the step where a baseline column stopped appearing).
    # Sits between the row-delta weight (0.6) and the column-count weight
    # (0.3): a column-set change is stronger evidence than a bare count
    # change because it is attributed to one operation, not inherited by
    # every operation downstream.
    MEMBERSHIP_WEIGHT = 0.4

    def __init__(self, tracker, thresholds: Dict[str, Any] = None):
        self._tracker = tracker
        self._thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._baseline: Optional[RunFingerprint] = None

    # ------------------------------------------------------------------
    # Fingerprinting
    # ------------------------------------------------------------------

    def fingerprint(self) -> RunFingerprint:
        """Create a fingerprint of the current run.

        Keys use ``operation:occurrence`` format so fingerprints remain
        comparable even when operations are inserted between runs.
        """
        fp = RunFingerprint()
        fp.total_records = len(self._tracker.records)
        occurrence: Dict[str, int] = {}
        seen: set = set()

        for rec in self._tracker.records:
            op = rec.operation
            occurrence[op] = occurrence.get(op, 0) + 1
            key = f"{op}:{occurrence[op]}"
            fp.operation_sequence.append(op)

            if rec.rows_before is not None and rec.rows_after is not None:
                fp.row_deltas[key] = rec.rows_after - rec.rows_before
            if rec.rows_before is not None:
                fp.rows_before[key] = rec.rows_before

            if rec.output_shape and len(rec.output_shape) > 1:
                fp.col_counts[key] = rec.output_shape[1]

            if rec.duration_ms is not None:
                fp.durations[key] = rec.duration_ms

            if rec.output_shape:
                fp.shapes[key] = list(rec.output_shape)

            cols = self._record_output_columns(rec)
            if cols is not None:
                fp.output_columns[key] = cols
                seen.update(cols)
            if rec.input_columns is not None and len(rec.input_columns) <= self.MAX_TRACKED_COLUMNS:
                seen.update(str(c) for c in rec.input_columns)
            if rec.columns_added:
                fp.columns_added[key] = [str(c) for c in rec.columns_added]
            if rec.columns_removed:
                fp.columns_removed[key] = [str(c) for c in rec.columns_removed]

            if rec.category == 'evaluate' and rec.metadata.get('metric_value') is not None:
                metric_name = rec.metadata.get('metric_name', rec.operation)
                value = rec.metadata['metric_value']
                fp.metric_runs.setdefault(metric_name, []).append(value)
                fp.metrics[metric_name] = value

        fp.columns_seen = sorted(seen)
        return fp

    def _record_output_columns(self, rec: TransformationRecord) -> Optional[List[str]]:
        """Column names the record produced, from the record itself or
        the tracker node it created. None when unknown or too wide."""
        cols = rec.output_columns
        if cols is None and rec.child_id:
            node = self._tracker.nodes.get(rec.child_id) if hasattr(self._tracker, 'nodes') else None
            if node and node.get('columns') is not None:
                cols = node['columns']
        if cols is None:
            return None
        if len(cols) > self.MAX_TRACKED_COLUMNS:
            return None
        return [str(c) for c in cols]

    def load_baseline(self, path: str) -> bool:
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                self._baseline = RunFingerprint.from_dict(data[-1])
            elif isinstance(data, dict):
                self._baseline = RunFingerprint.from_dict(data)
            return self._baseline is not None
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return False

    def set_baseline(self, fp: RunFingerprint) -> None:
        self._baseline = fp

    def save_fingerprint(self, path: str, append: bool = True) -> None:
        fp = self.fingerprint()
        history = []
        if append and os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    history = json.load(f)
                if not isinstance(history, list):
                    history = [history]
            except (json.JSONDecodeError, FileNotFoundError):
                history = []
        history.append(fp.to_dict())
        history = history[-50:]
        with open(path, 'w') as f:
            json.dump(history, f, indent=2, default=str)

    # ------------------------------------------------------------------
    # Anomaly Detection
    # ------------------------------------------------------------------

    def detect_anomalies(self, baseline: RunFingerprint = None) -> List[Anomaly]:
        bl = baseline or self._baseline
        if bl is None:
            return self._detect_self_anomalies()

        current = self.fingerprint()
        anomalies: List[Anomaly] = []
        anomalies.extend(self._check_operation_sequence(bl, current))
        anomalies.extend(self._check_row_deltas(bl, current))
        anomalies.extend(self._check_col_counts(bl, current))
        anomalies.extend(self._check_column_sets(bl, current))
        anomalies.extend(self._check_metrics(bl, current))
        anomalies.extend(self._check_durations(bl, current))

        severity_order = {'critical': 0, 'warning': 1, 'info': 2}
        anomalies.sort(key=lambda a: severity_order.get(a.severity, 3))
        return anomalies

    # ------------------------------------------------------------------
    # Column-set membership
    # ------------------------------------------------------------------

    def _column_set_changes(self, bl: RunFingerprint, cur: RunFingerprint) -> Dict[str, Dict[str, Any]]:
        """Attribute column-set differences to the operation that caused them.

        Three signals, each credited to exactly one operation so that the
        operations downstream, which merely inherit the changed column
        set, are not blamed for it:

        * **introduced** -- a column the current run produced that the
          baseline never saw in any input or output. Attributed to the
          first current operation whose output contains it. (A one-hot
          encoding of the wrong column creates hundreds of these.)
        * **retained** -- a column the baseline deliberately removed
          (it appears in some baseline ``columns_removed``) that the
          current run never removes and that reaches a current output.
          Attributed to the first current operation whose output
          contains it. (A label column that never got dropped: target
          leakage.)
        * **missing** -- a column the baseline created (it appears in
          some baseline ``columns_added``) that the current run never
          creates. Attributed to the baseline operation that created it,
          by key.

        Working from whole-run sets rather than per-key output sets keeps
        the attribution stable when an operation is inserted or removed
        between runs, which shifts every ``op:occurrence`` key after it.

        Returns ``{'introduced': {key: [cols]}, 'retained': {key: {col:
        baseline_op_that_removed_it}}, 'missing': {key: [cols]}}``.
        """
        result: Dict[str, Dict[str, Any]] = {'introduced': {}, 'retained': {}, 'missing': {}}
        if not self._thresholds.get('column_membership', True):
            return result
        if not bl.has_column_sets() or not cur.has_column_sets():
            return result

        bl_seen = set(bl.columns_seen)
        cur_seen = set(cur.columns_seen)
        bl_removed: Dict[str, str] = {}
        for key, cols in bl.columns_removed.items():
            for c in cols:
                bl_removed.setdefault(c, key.rsplit(':', 1)[0])
        cur_removed = {c for cols in cur.columns_removed.values() for c in cols}
        bl_added = {c for cols in bl.columns_added.values() for c in cols}
        cur_added = {c for cols in cur.columns_added.values() for c in cols}

        novel = cur_seen - bl_seen
        retained = {c for c in bl_removed if c not in cur_removed}
        vanished = bl_added - cur_added

        if novel or retained:
            seen_novel: set = set()
            seen_ret: set = set()
            for key in cur.keys_in_order():
                cols = cur.output_columns.get(key)
                if not cols:
                    continue
                cols_set = set(cols)
                new = (cols_set & novel) - seen_novel
                if new:
                    result['introduced'][key] = sorted(new)
                    seen_novel |= new
                kept = (cols_set & retained) - seen_ret
                if kept:
                    result['retained'][key] = {c: bl_removed[c] for c in sorted(kept)}
                    seen_ret |= kept

        if vanished:
            seen_gone: set = set()
            for key in bl.keys_in_order():
                cols = bl.columns_added.get(key)
                if not cols:
                    continue
                gone = (set(cols) & vanished) - seen_gone
                if gone:
                    result['missing'][key] = sorted(gone)
                    seen_gone |= gone

        return result

    def _check_column_sets(self, bl, cur) -> List[Anomaly]:
        anomalies = []
        changes = self._column_set_changes(bl, cur)
        step_of = {key: i for i, key in enumerate(cur.keys_in_order())}

        for key, cols in changes['introduced'].items():
            op_name = key.rsplit(':', 1)[0]
            anomalies.append(Anomaly(
                severity="critical" if len(cols) >= 10 else "warning",
                operation=op_name, step_index=step_of.get(key, -1),
                metric="columns_introduced", expected="absent",
                actual=self._name_list(cols), deviation=len(cols),
                message=f"{op_name} introduced {len(cols)} column(s) the baseline "
                        f"never saw: {self._name_list(cols)}",
            ))

        for key, kept in changes['retained'].items():
            op_name = key.rsplit(':', 1)[0]
            cols = sorted(kept)
            removed_by = sorted({kept[c] for c in cols})
            anomalies.append(Anomaly(
                severity="critical",
                operation=op_name, step_index=step_of.get(key, -1),
                metric="columns_retained", expected="removed",
                actual=self._name_list(cols), deviation=len(cols),
                message=f"{self._name_list(cols)} removed by {', '.join(removed_by)} in the "
                        f"baseline but never removed in this run; first present at {op_name}",
            ))

        for key, cols in changes['missing'].items():
            op_name = key.rsplit(':', 1)[0]
            anomalies.append(Anomaly(
                severity="critical" if len(cols) >= 10 else "warning",
                operation=op_name, step_index=step_of.get(key, -1),
                metric="columns_missing", expected=self._name_list(cols),
                actual="absent", deviation=len(cols),
                message=f"{len(cols)} column(s) {op_name} created in the baseline "
                        f"were never created in this run: {self._name_list(cols)}",
            ))
        return anomalies

    @staticmethod
    def _name_list(cols: List[str], limit: int = 5, total: int = None) -> str:
        total = len(cols) if total is None else total
        shown = ', '.join(list(cols)[:limit])
        if total > limit:
            shown += f", ... (+{total - limit} more)"
        return shown

    def _detect_self_anomalies(self) -> List[Anomaly]:
        """Detect anomalies within a single run (no baseline needed)."""
        anomalies = []

        for i, rec in enumerate(self._tracker.records):
            # Large row drops
            if rec.rows_before and rec.rows_after and rec.rows_before > 0:
                drop_pct = (1 - rec.rows_after / rec.rows_before) * 100
                if drop_pct > 50:
                    severity = "critical" if drop_pct > 95 else "warning"
                    anomalies.append(Anomaly(
                        severity=severity, operation=rec.operation, step_index=i,
                        metric="row_drop_percent", expected="<50%",
                        actual=f"{drop_pct:.1f}%", deviation=drop_pct,
                        message=f"{rec.operation} removed {drop_pct:.1f}% of rows "
                                f"({rec.rows_before:,} -> {rec.rows_after:,})",
                    ))

            # Training on very few samples
            if rec.category == 'train' and rec.rows_before and rec.rows_before < 100:
                anomalies.append(Anomaly(
                    severity="warning", operation=rec.operation, step_index=i,
                    metric="training_size", expected=">100",
                    actual=rec.rows_before, deviation=0,
                    message=f"{rec.operation} trained on only {rec.rows_before} samples",
                ))

            # Suspicious metric values
            if rec.category == 'evaluate':
                val = rec.metadata.get('metric_value')
                if val is not None:
                    name = rec.metadata.get('metric_name', rec.operation)
                    if val == 0.0:
                        anomalies.append(Anomaly(
                            severity="critical", operation=rec.operation, step_index=i,
                            metric=name, expected=">0", actual=0.0, deviation=100,
                            message=f"{name} = 0.0 (model may not be learning)",
                        ))
                    elif val == 1.0 and name in ('accuracy_score', 'f1_score', 'r2_score'):
                        anomalies.append(Anomaly(
                            severity="warning", operation=rec.operation, step_index=i,
                            metric=name, expected="<1.0", actual=1.0, deviation=0,
                            message=f"{name} = 1.0 (possible data leakage or overfitting)",
                        ))

        return anomalies

    def _check_operation_sequence(self, bl, cur) -> List[Anomaly]:
        anomalies = []
        bl_ops = set(bl.operation_sequence)
        cur_ops = set(cur.operation_sequence)

        if self._thresholds.get('new_operation'):
            for op in cur_ops - bl_ops:
                anomalies.append(Anomaly(
                    severity="info", operation=op, step_index=-1,
                    metric="operation_added", expected="absent", actual="present",
                    deviation=0, message=f"New operation '{op}' not seen in baseline",
                ))

        if self._thresholds.get('missing_operation'):
            for op in bl_ops - cur_ops:
                anomalies.append(Anomaly(
                    severity="warning", operation=op, step_index=-1,
                    metric="operation_missing", expected="present", actual="absent",
                    deviation=0, message=f"Operation '{op}' from baseline is missing",
                ))

        if cur.total_records != bl.total_records:
            anomalies.append(Anomaly(
                severity="info", operation="pipeline", step_index=-1,
                metric="operation_count", expected=bl.total_records,
                actual=cur.total_records,
                deviation=abs(cur.total_records - bl.total_records),
                message=f"Pipeline has {cur.total_records} ops (baseline: {bl.total_records})",
            ))
        return anomalies

    def _check_row_deltas(self, bl, cur) -> List[Anomaly]:
        anomalies = []
        threshold = self._thresholds.get('row_delta_pct', 20.0)
        partners = _partner_keys(
            bl.operation_sequence, cur.operation_sequence, bl.row_deltas, cur.row_deltas,
        )

        for key, cur_delta in cur.row_deltas.items():
            op_name = key.rsplit(':', 1)[0]
            partner = partners.get(key)
            if partner is None or partner not in bl.row_deltas:
                before = cur.rows_before.get(key)
                if before and cur_delta < 0:
                    frac = abs(cur_delta) / before * 100
                    if frac >= threshold / 4:
                        anomalies.append(Anomaly(
                            severity="critical" if frac > 50 else "warning",
                            operation=op_name, step_index=-1,
                            metric="row_delta", expected=0, actual=cur_delta,
                            deviation=frac,
                            message=(
                                f"New operation '{op_name}' removed {frac:.0f}% of rows "
                                f"({before:,} -> {before + cur_delta:,})"
                            ),
                        ))
                continue
            bl_delta = bl.row_deltas[partner]
            cur_before = cur.rows_before.get(key)
            bl_before = bl.rows_before.get(partner)
            if cur_before and bl_before:
                cur_rate = cur_delta / cur_before
                bl_rate = bl_delta / bl_before
                if abs(bl_rate) < 1e-9:
                    if abs(cur_rate) < 0.01:
                        continue
                    pct_change = abs(cur_rate) * 100
                else:
                    pct_change = abs((cur_rate - bl_rate) / bl_rate) * 100
            elif bl_delta == 0:
                if cur_delta != 0:
                    anomalies.append(Anomaly(
                        severity="warning", operation=op_name, step_index=-1,
                        metric="row_delta", expected=0, actual=cur_delta,
                        deviation=abs(cur_delta),
                        message=f"{op_name} changed {cur_delta:+,d} rows (baseline: no change)",
                    ))
                continue
            else:
                pct_change = abs((cur_delta - bl_delta) / abs(bl_delta)) * 100

            if pct_change > threshold:
                severity = "critical" if pct_change > threshold * 3 else "warning"
                anomalies.append(Anomaly(
                    severity=severity, operation=op_name, step_index=-1,
                    metric="row_delta", expected=bl_delta, actual=cur_delta,
                    deviation=pct_change,
                    message=f"{op_name} row change: {cur_delta:+,d} "
                            f"(baseline: {bl_delta:+,d}, {pct_change:.0f}% deviation)",
                ))
        return anomalies

    def _check_col_counts(self, bl, cur) -> List[Anomaly]:
        anomalies = []
        for key, cur_cols in cur.col_counts.items():
            if key not in bl.col_counts:
                continue
            bl_cols = bl.col_counts[key]
            if cur_cols != bl_cols:
                op_name = key.rsplit(':', 1)[0]
                anomalies.append(Anomaly(
                    severity="warning", operation=op_name, step_index=-1,
                    metric="column_count", expected=bl_cols, actual=cur_cols,
                    deviation=abs(cur_cols - bl_cols),
                    message=f"{op_name} output has {cur_cols} columns (baseline: {bl_cols})",
                ))
        return anomalies

    def _metric_pairs(self, bl: RunFingerprint, cur: RunFingerprint):
        """``(label, metric_name, baseline_value, current_value)`` in call order.

        Repeated calls of the same metric are compared occurrence by
        occurrence. Fingerprints written before ``metric_runs`` existed
        compare the single stored value.
        """
        if bl.metric_runs and cur.metric_runs:
            for name in bl.metric_runs.keys() & cur.metric_runs.keys():
                bl_vals = bl.metric_runs[name]
                cur_vals = cur.metric_runs[name]
                multi = max(len(bl_vals), len(cur_vals)) > 1
                for i, (bl_val, cur_val) in enumerate(zip(bl_vals, cur_vals), start=1):
                    label = f"{name} #{i}" if multi else name
                    yield label, name, bl_val, cur_val
            return
        for name, cur_val in cur.metrics.items():
            if name in bl.metrics:
                yield name, name, bl.metrics[name], cur_val

    def _check_metrics(self, bl, cur) -> List[Anomaly]:
        anomalies = []
        threshold = self._thresholds.get('metric_drop_pct', 5.0)

        for label, name, bl_val, cur_val in self._metric_pairs(bl, cur):
            if bl_val == 0:
                continue
            pct_change = ((cur_val - bl_val) / abs(bl_val)) * 100
            if pct_change < -threshold:
                anomalies.append(Anomaly(
                    severity="critical" if abs(pct_change) > threshold * 3 else "warning",
                    operation=name, step_index=-1, metric=name,
                    expected=bl_val, actual=cur_val, deviation=abs(pct_change),
                    message=f"{label} dropped from {bl_val:.4f} to {cur_val:.4f} ({pct_change:+.1f}%)",
                ))
        return anomalies

    def _check_durations(self, bl, cur) -> List[Anomaly]:
        anomalies = []
        threshold = self._thresholds.get('duration_spike_pct', 200.0)

        for key, cur_dur in cur.durations.items():
            if key not in bl.durations:
                continue
            bl_dur = bl.durations[key]
            # A few milliseconds of timer noise is not a pipeline change.
            if bl_dur < 50.0:
                continue
            pct_change = ((cur_dur - bl_dur) / bl_dur) * 100
            if pct_change > threshold:
                op_name = key.rsplit(':', 1)[0]
                anomalies.append(Anomaly(
                    severity="info", operation=op_name, step_index=-1,
                    metric="duration_ms", expected=f"{bl_dur:.0f}ms",
                    actual=f"{cur_dur:.0f}ms", deviation=pct_change,
                    message=f"{op_name} took {cur_dur:.0f}ms (baseline: {bl_dur:.0f}ms, +{pct_change:.0f}%)",
                ))
        return anomalies

    # ------------------------------------------------------------------
    # Root Cause Localization
    # ------------------------------------------------------------------

    def localize_root_cause(self, metric_name: str = None,
                            baseline: RunFingerprint = None) -> Optional[RootCause]:
        self._last_ranking = []
        bl = baseline or self._baseline
        cur = self.fingerprint()

        if not bl:
            return self._localize_without_baseline()
        selected = self._select_metric_pair(bl, cur, metric_name)
        if selected is None:
            if metric_name:
                return self._localize_without_baseline()
            fell, rose = self._metric_movements(bl, cur)
            if fell:
                # The drop is real but under the 5% warning line. A row-rate
                # change still has to be named; the warning threshold is for
                # the anomaly list, not for refusing to point at a line.
                _drop, name, label, bl_val, cur_val = max(fell)
                selected = (name, label, bl_val, cur_val, True)
            elif rose:
                # A rise is not a row-drop cause. Column changes can still be.
                selected = ("pipeline", "pipeline", None, None, False)
            else:
                return None
        metric_name, metric_label, metric_bl, metric_cur, metric_fell = selected

        # Score each transformation by deviation from baseline
        scores = []
        occurrence: Dict[str, int] = {}
        changes = self._column_set_changes(bl, cur)
        partners = _partner_keys(
            bl.operation_sequence, cur.operation_sequence, bl.row_deltas, cur.row_deltas,
        )

        for i, rec in enumerate(self._tracker.records):
            if rec.category == 'evaluate':
                continue

            op = rec.operation
            occurrence[op] = occurrence.get(op, 0) + 1
            key = f"{op}:{occurrence[op]}"
            partner = partners.get(key)
            score = 0.0
            evidence = {}

            # Column-set membership: credited only to the operation where
            # the change originated, never to the operations downstream
            # that merely inherit the changed column set.
            if key in changes['introduced']:
                cols = changes['introduced'][key]
                score += self.MEMBERSHIP_WEIGHT
                evidence['columns_introduced'] = cols[:10]
                evidence['n_columns_introduced'] = len(cols)
            if key in changes['retained']:
                kept = changes['retained'][key]
                score += self.MEMBERSHIP_WEIGHT
                evidence['columns_retained'] = sorted(kept)[:10]
                evidence['n_columns_retained'] = len(kept)
                evidence['retained_removed_by'] = sorted({kept[c] for c in kept})
            if key in changes['missing']:
                cols = changes['missing'][key]
                score += self.MEMBERSHIP_WEIGHT
                evidence['columns_missing'] = cols[:10]
                evidence['n_columns_missing'] = len(cols)

            row_score, row_evidence = self._row_cause_score(key, partner, bl, cur)
            score += row_score
            evidence.update(row_evidence)

            if partner and key in cur.col_counts and partner in bl.col_counts:
                if cur.col_counts[key] != bl.col_counts[partner]:
                    score += 0.3
                    evidence['col_baseline'] = bl.col_counts[partner]
                    evidence['col_current'] = cur.col_counts[key]

            if partner is None:
                score += 0.1
                evidence['new_operation'] = True

            if score > 0:
                scores.append((i, score, rec.operation, evidence))

        # A metric that did not fall is only localized when a column change
        # explains it (a leaked label, a wrong one-hot). A row-count shift
        # on a metric that rose is not a cause.
        if not metric_fell:
            structural = (
                'columns_introduced', 'columns_retained',
                'columns_missing', 'col_baseline',
            )
            scores = [s for s in scores if any(k in s[3] for k in structural)]

        if not scores:
            return None

        scores.sort(key=lambda x: x[1], reverse=True)
        self._last_ranking = _ranking_from_scores(self._tracker, scores)
        idx, score, op, evidence = scores[0]
        normalized = min(score, 1.0)

        return RootCause(
            metric_name=metric_name, metric_baseline=metric_bl,
            metric_actual=metric_cur, root_operation=op,
            root_step_index=idx, impact_score=normalized,
            explanation=self._explain_root_cause(op, idx, evidence, metric_label, metric_bl, metric_cur),
            evidence=evidence,
        )

    def ranked_causes(self, metric_name: str = None,
                      baseline: RunFingerprint = None) -> List[Dict[str, Any]]:
        """Scored operations, best first.

        The first entry is the operation ``localize_root_cause`` names.
        ``source_line`` is the line in the caller's file that issued the
        call, when the hook recorded one. Top-3 localization is membership
        of the mutated line in the first three entries.
        """
        self.localize_root_cause(metric_name, baseline)
        return list(getattr(self, "_last_ranking", []))

    def _localize_without_baseline(self) -> Optional[RootCause]:
        largest_drop_idx, largest_drop_pct = -1, 0

        for i, rec in enumerate(self._tracker.records):
            if rec.rows_before and rec.rows_after and rec.rows_before > 0:
                drop_pct = (1 - rec.rows_after / rec.rows_before) * 100
                if drop_pct > largest_drop_pct:
                    largest_drop_pct = drop_pct
                    largest_drop_idx = i

        if largest_drop_idx < 0 or largest_drop_pct < 20:
            self._last_ranking = []
            return None

        rec = self._tracker.records[largest_drop_idx]
        bad_metric = None
        for r in self._tracker.records:
            if r.category == 'evaluate' and r.metadata.get('metric_value') is not None:
                if r.metadata['metric_value'] < 0.1:
                    bad_metric = r.metadata.get('metric_name', r.operation)
                    break

        evidence = {
            'rows_before': rec.rows_before, 'rows_after': rec.rows_after,
            'drop_percent': largest_drop_pct,
        }
        self._last_ranking = _ranking_from_scores(self._tracker, [(
            largest_drop_idx, largest_drop_pct / 100, rec.operation, evidence,
        )])
        return RootCause(
            metric_name=bad_metric or "unknown",
            metric_baseline=0, metric_actual=0,
            root_operation=rec.operation, root_step_index=largest_drop_idx,
            impact_score=largest_drop_pct / 100,
            explanation=(
                f"{rec.operation} at step {largest_drop_idx} removed "
                f"{largest_drop_pct:.1f}% of data "
                f"({rec.rows_before:,} -> {rec.rows_after:,} rows). "
                f"This is the most likely cause of downstream metric degradation."
            ),
            evidence=evidence,
        )

    def _select_metric_pair(self, bl: RunFingerprint, cur: RunFingerprint,
                            metric_name: Optional[str]):
        """Pick the metric occurrence to explain.

        Returns ``(name, label, baseline, current, fell)``. ``fell`` is
        true when that occurrence dropped past ``metric_drop_pct``. When a
        name is requested and none of its calls dropped, the last call is
        returned with ``fell=False``. When no name is requested and nothing
        dropped, returns None.
        """
        pairs = [p for p in self._metric_pairs(bl, cur) if metric_name is None or p[1] == metric_name]
        if not pairs:
            return None
        threshold = self._thresholds.get('metric_drop_pct', 5.0) / 100.0
        worst = None
        worst_drop = 0.0
        for label, name, bl_val, cur_val in pairs:
            if not bl_val:
                continue
            drop = (bl_val - cur_val) / abs(bl_val)
            if drop > threshold and drop > worst_drop:
                worst_drop = drop
                worst = (name, label, bl_val, cur_val, True)
        if worst is not None:
            return worst
        if metric_name is None:
            return None
        label, name, bl_val, cur_val = pairs[-1]
        return (name, label, bl_val, cur_val, False)

    def _metric_movements(self, bl: RunFingerprint, cur: RunFingerprint):
        """Drops and whether any metric rose, ignoring moves under 1e-6.

        Each drop is ``(fraction, name, label, baseline, current)``. A rise
        with no drop is the type-coercion case: a row shift is not the cause.
        """
        fell = []
        rose = False
        for label, name, bl_val, cur_val in self._metric_pairs(bl, cur):
            if not isinstance(bl_val, (int, float)) or isinstance(bl_val, bool):
                continue
            if isinstance(cur_val, bool) or not isinstance(cur_val, (int, float)):
                continue
            if bl_val == 0:
                continue
            drop = (bl_val - cur_val) / abs(bl_val)
            if drop > 1e-6:
                fell.append((drop, name, label, bl_val, cur_val))
            elif drop < -1e-6:
                rose = True
        return fell, rose

    def _row_cause_score(self, key, partner, bl: RunFingerprint, cur: RunFingerprint):
        """Score one operation's row change.

        ``partner`` is the baseline key this step continues, or None when
        the alignment left it unmatched. An unmatched step that removed
        rows is an insert, including a second filter when the baseline
        already has one. A matched step is scored by the change in its
        row-change *rate* when both fingerprints know ``rows_before``, so a
        split that stays at the same ratio does not outrank the filter that
        shrank its input. Older fingerprints fall back to the absolute delta.
        """
        score = 0.0
        evidence: Dict[str, Any] = {}
        cur_d = cur.row_deltas.get(key)
        if cur_d is None:
            return score, evidence
        cur_before = cur.rows_before.get(key) if cur.rows_before else None
        bl_before = bl.rows_before.get(partner) if partner and bl.rows_before else None

        if partner is None or partner not in bl.row_deltas:
            if cur_before and cur_d < 0:
                frac = abs(cur_d) / cur_before
                if frac >= 0.05:
                    score += 0.55 + min(frac, 1.0)
                    evidence['introduced_row_drop'] = cur_d
                    evidence['rows_before'] = cur_before
                    evidence['rows_after'] = cur_before + cur_d
                    evidence['new_operation'] = True
            return score, evidence

        bl_d = bl.row_deltas.get(partner)

        if cur_before and bl_before:
            cur_rate = cur_d / cur_before
            bl_rate = bl_d / bl_before
            if abs(bl_rate) < 1e-9:
                if abs(cur_rate) >= 0.05:
                    score += 0.5
                    evidence['unexpected_row_change'] = cur_d
            else:
                rate_dev = abs((cur_rate - bl_rate) / bl_rate)
                if rate_dev > 0.20:
                    score += rate_dev * 0.6
                    evidence['row_delta_baseline'] = bl_d
                    evidence['row_delta_current'] = cur_d
            return score, evidence

        if bl_d == 0:
            if cur_d != 0:
                score += 0.5
                evidence['unexpected_row_change'] = cur_d
        else:
            deviation = abs((cur_d - bl_d) / abs(bl_d))
            score += deviation * 0.6
            evidence['row_delta_baseline'] = bl_d
            evidence['row_delta_current'] = cur_d
        return score, evidence

    @staticmethod
    def _explain_root_cause(op, idx, evidence, metric_name, bl_val, cur_val):
        if bl_val is None or cur_val is None:
            parts = [f"The most likely cause is '{op}' at step {idx}. "]
        else:
            direction = "drop" if cur_val < bl_val else "increase"
            parts = [f"The most likely cause of the {metric_name} {direction} "]
            parts.append(f"(from {bl_val:.4f} to {cur_val:.4f}) ")
            parts.append(f"is '{op}' at step {idx}. ")
        if 'introduced_row_drop' in evidence:
            parts.append(
                f"It removed {abs(evidence['introduced_row_drop']):,.0f} rows "
                f"({evidence['rows_before']:,} -> {evidence['rows_after']:,}) "
                f"and was not in the baseline. ")
        if 'row_delta_baseline' in evidence:
            parts.append(
                f"Row change was {evidence['row_delta_current']:+,d} "
                f"(baseline: {evidence['row_delta_baseline']:+,d}). ")
        if 'col_baseline' in evidence:
            parts.append(
                f"Column count changed from {evidence['col_baseline']} "
                f"to {evidence['col_current']}. ")
        if 'columns_introduced' in evidence:
            n = evidence.get('n_columns_introduced', len(evidence['columns_introduced']))
            parts.append(
                f"It introduced {n} column(s) the baseline never saw: "
                f"{LineageAnalyzer._name_list(evidence['columns_introduced'], total=n)}. ")
        if 'columns_retained' in evidence:
            n = evidence.get('n_columns_retained', len(evidence['columns_retained']))
            by = ', '.join(evidence.get('retained_removed_by', []))
            parts.append(
                f"Column(s) {LineageAnalyzer._name_list(evidence['columns_retained'], total=n)} "
                f"were removed by {by} in the baseline but are never removed in this run. ")
        if 'columns_missing' in evidence:
            n = evidence.get('n_columns_missing', len(evidence['columns_missing']))
            parts.append(
                f"{n} column(s) it created in the baseline were never created: "
                f"{LineageAnalyzer._name_list(evidence['columns_missing'], total=n)}. ")
        if evidence.get('new_operation') and 'introduced_row_drop' not in evidence:
            parts.append("This operation was not present in the baseline. ")
        return ''.join(parts)
