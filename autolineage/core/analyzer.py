"""
Lineage Analyzer: Anomaly Detection and Root Cause Localization.

Primary research contribution. Actively DETECTS when a pipeline's
behavior deviates from baseline and LOCALIZES which transformation
caused the problem. No existing tool does this on ML pipeline lineage.
"""

import json
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple

from . import TransformationRecord


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
    """Compact summary of a pipeline run for comparison."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    total_records: int = 0
    operation_sequence: List[str] = field(default_factory=list)
    row_deltas: Dict[str, int] = field(default_factory=dict)
    col_counts: Dict[str, int] = field(default_factory=dict)
    durations: Dict[str, float] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    shapes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> 'RunFingerprint':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


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
    }

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

        for rec in self._tracker.records:
            op = rec.operation
            occurrence[op] = occurrence.get(op, 0) + 1
            key = f"{op}:{occurrence[op]}"
            fp.operation_sequence.append(op)

            if rec.rows_before is not None and rec.rows_after is not None:
                fp.row_deltas[key] = rec.rows_after - rec.rows_before

            if rec.output_shape and len(rec.output_shape) > 1:
                fp.col_counts[key] = rec.output_shape[1]

            if rec.duration_ms is not None:
                fp.durations[key] = rec.duration_ms

            if rec.output_shape:
                fp.shapes[key] = list(rec.output_shape)

            if rec.category == 'evaluate' and rec.metadata.get('metric_value') is not None:
                metric_name = rec.metadata.get('metric_name', rec.operation)
                fp.metrics[metric_name] = rec.metadata['metric_value']

        return fp

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
        anomalies.extend(self._check_metrics(bl, current))
        anomalies.extend(self._check_durations(bl, current))

        severity_order = {'critical': 0, 'warning': 1, 'info': 2}
        anomalies.sort(key=lambda a: severity_order.get(a.severity, 3))
        return anomalies

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

        for key, cur_delta in cur.row_deltas.items():
            if key not in bl.row_deltas:
                continue
            bl_delta = bl.row_deltas[key]
            op_name = key.rsplit(':', 1)[0]

            if bl_delta == 0:
                if cur_delta != 0:
                    anomalies.append(Anomaly(
                        severity="warning", operation=op_name, step_index=-1,
                        metric="row_delta", expected=0, actual=cur_delta,
                        deviation=abs(cur_delta),
                        message=f"{op_name} changed {cur_delta:+,d} rows (baseline: no change)",
                    ))
                continue

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

    def _check_metrics(self, bl, cur) -> List[Anomaly]:
        anomalies = []
        threshold = self._thresholds.get('metric_drop_pct', 5.0)

        for name, cur_val in cur.metrics.items():
            if name not in bl.metrics:
                continue
            bl_val = bl.metrics[name]
            if bl_val == 0:
                continue
            pct_change = ((cur_val - bl_val) / abs(bl_val)) * 100
            if pct_change < -threshold:
                anomalies.append(Anomaly(
                    severity="critical" if abs(pct_change) > threshold * 3 else "warning",
                    operation=name, step_index=-1, metric=name,
                    expected=bl_val, actual=cur_val, deviation=abs(pct_change),
                    message=f"{name} dropped from {bl_val:.4f} to {cur_val:.4f} ({pct_change:+.1f}%)",
                ))
        return anomalies

    def _check_durations(self, bl, cur) -> List[Anomaly]:
        anomalies = []
        threshold = self._thresholds.get('duration_spike_pct', 200.0)

        for key, cur_dur in cur.durations.items():
            if key not in bl.durations:
                continue
            bl_dur = bl.durations[key]
            if bl_dur < 1.0:
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
        bl = baseline or self._baseline
        cur = self.fingerprint()

        if metric_name and metric_name in cur.metrics:
            if bl and metric_name in bl.metrics:
                metric_bl = bl.metrics[metric_name]
                metric_cur = cur.metrics[metric_name]
            else:
                return self._localize_without_baseline()
        elif bl:
            worst_name, worst_drop = None, 0
            for name, cur_val in cur.metrics.items():
                if name in bl.metrics and bl.metrics[name] > 0:
                    drop = (bl.metrics[name] - cur_val) / abs(bl.metrics[name])
                    if drop > worst_drop:
                        worst_drop = drop
                        worst_name = name
            if worst_name is None:
                return None
            metric_name = worst_name
            metric_bl = bl.metrics[metric_name]
            metric_cur = cur.metrics[metric_name]
        else:
            return self._localize_without_baseline()

        # Score each transformation by deviation from baseline
        scores = []
        occurrence: Dict[str, int] = {}

        for i, rec in enumerate(self._tracker.records):
            if rec.category == 'evaluate':
                continue

            op = rec.operation
            occurrence[op] = occurrence.get(op, 0) + 1
            key = f"{op}:{occurrence[op]}"
            score = 0.0
            evidence = {}

            if key in cur.row_deltas and key in bl.row_deltas:
                cur_d = cur.row_deltas[key]
                bl_d = bl.row_deltas[key]
                if bl_d != 0:
                    deviation = abs((cur_d - bl_d) / abs(bl_d))
                    score += deviation * 0.6
                    evidence['row_delta_baseline'] = bl_d
                    evidence['row_delta_current'] = cur_d
                elif cur_d != 0:
                    score += 0.5
                    evidence['unexpected_row_change'] = cur_d

            if key in cur.col_counts and key in bl.col_counts:
                if cur.col_counts[key] != bl.col_counts[key]:
                    score += 0.3
                    evidence['col_baseline'] = bl.col_counts[key]
                    evidence['col_current'] = cur.col_counts[key]

            if rec.operation not in bl.operation_sequence:
                score += 0.1
                evidence['new_operation'] = True

            if score > 0:
                scores.append((i, score, rec.operation, evidence))

        if not scores:
            return None

        scores.sort(key=lambda x: x[1], reverse=True)
        idx, score, op, evidence = scores[0]
        normalized = min(score, 1.0)

        return RootCause(
            metric_name=metric_name, metric_baseline=metric_bl,
            metric_actual=metric_cur, root_operation=op,
            root_step_index=idx, impact_score=normalized,
            explanation=self._explain_root_cause(op, idx, evidence, metric_name, metric_bl, metric_cur),
            evidence=evidence,
        )

    def _localize_without_baseline(self) -> Optional[RootCause]:
        largest_drop_idx, largest_drop_pct = -1, 0

        for i, rec in enumerate(self._tracker.records):
            if rec.rows_before and rec.rows_after and rec.rows_before > 0:
                drop_pct = (1 - rec.rows_after / rec.rows_before) * 100
                if drop_pct > largest_drop_pct:
                    largest_drop_pct = drop_pct
                    largest_drop_idx = i

        if largest_drop_idx < 0 or largest_drop_pct < 20:
            return None

        rec = self._tracker.records[largest_drop_idx]
        bad_metric = None
        for r in self._tracker.records:
            if r.category == 'evaluate' and r.metadata.get('metric_value') is not None:
                if r.metadata['metric_value'] < 0.1:
                    bad_metric = r.metadata.get('metric_name', r.operation)
                    break

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
            evidence={'rows_before': rec.rows_before, 'rows_after': rec.rows_after,
                      'drop_percent': largest_drop_pct},
        )

    @staticmethod
    def _explain_root_cause(op, idx, evidence, metric_name, bl_val, cur_val):
        parts = [f"The most likely cause of {metric_name} degradation "]
        parts.append(f"(from {bl_val:.4f} to {cur_val:.4f}) ")
        parts.append(f"is '{op}' at step {idx}. ")
        if 'row_delta_baseline' in evidence:
            parts.append(
                f"Row change was {evidence['row_delta_current']:+,d} "
                f"(baseline: {evidence['row_delta_baseline']:+,d}). ")
        if 'col_baseline' in evidence:
            parts.append(
                f"Column count changed from {evidence['col_baseline']} "
                f"to {evidence['col_current']}. ")
        if evidence.get('new_operation'):
            parts.append("This operation was not present in the baseline. ")
        return ''.join(parts)
