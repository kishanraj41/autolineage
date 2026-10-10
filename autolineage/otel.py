"""OpenTelemetry export: one span per tracked operation.

Install with ``pip install "autolineage[otel]"``. Spans go wherever your
OpenTelemetry tracer provider sends them (OTLP collector, Jaeger, Tempo,
Honeycomb, the console...); AutoLineage does not configure an exporter.

    import autolineage.auto
    from autolineage.otel import enable_otel_export

    exporter = enable_otel_export()          # uses the global tracer provider
    ... your pipeline ...
    exporter.shutdown()                      # optional: ends the run span

Every recorded operation becomes a span named ``<library>.<operation>``
(``pandas-transforms.merge``, ``sklearn.f1_score``), timed by the
operation's measured duration, and nested under one ``autolineage.run``
span per call to ``enable_otel_export``. Lineage is a DAG, not a tree, so
data dependencies are carried as attributes rather than span nesting:
``autolineage.child_id`` is the lineage ID of the operation's output and
``autolineage.parent_ids`` the IDs of its inputs, which lets a backend
join operations across services that share lineage IDs (for example via
RudriQ). This is how a pipeline split across processes or machines can be
correlated: each process exports its spans, the IDs line up.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

_INSTALL_HINT = 'OpenTelemetry is not installed. Run: pip install "autolineage[otel]"'
_MAX_COLUMNS = 50   # cap list attributes so a 400-column one-hot can't bloat a span


def _require_otel():
    try:
        from opentelemetry import trace  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(_INSTALL_HINT) from exc
    return trace


def record_attributes(rec) -> Dict[str, Any]:
    """OpenTelemetry attributes for one TransformationRecord.

    Only primitive values and homogeneous lists of strings/numbers, as the
    OpenTelemetry attribute spec requires; ``None`` fields are omitted.
    """
    attrs: Dict[str, Any] = {
        "autolineage.record_id": rec.id,
        "autolineage.library": rec.library,
        "autolineage.category": rec.category,
        "autolineage.operation": rec.operation,
        "autolineage.child_id": rec.child_id,
        "autolineage.parent_ids": [str(p) for p in rec.parent_ids if p],
    }
    if rec.rows_before is not None:
        attrs["autolineage.rows_before"] = int(rec.rows_before)
    if rec.rows_after is not None:
        attrs["autolineage.rows_after"] = int(rec.rows_after)
    if rec.row_delta is not None:
        attrs["autolineage.row_delta"] = int(rec.row_delta)
    if rec.input_shape:
        attrs["autolineage.input_shape"] = [int(x) for x in rec.input_shape]
    if rec.output_shape:
        attrs["autolineage.output_shape"] = [int(x) for x in rec.output_shape]
    for field in ("columns_added", "columns_removed"):
        cols = getattr(rec, field)
        if cols:
            attrs[f"autolineage.{field}"] = [str(c) for c in cols[:_MAX_COLUMNS]]
            attrs[f"autolineage.{field}_count"] = len(cols)
    if rec.duration_ms is not None:
        attrs["autolineage.duration_ms"] = float(rec.duration_ms)
    if rec.content_hash:
        attrs["autolineage.content_hash"] = str(rec.content_hash)
    md = rec.metadata or {}
    if md.get("metric_name") is not None:
        attrs["autolineage.metric_name"] = str(md["metric_name"])
    if isinstance(md.get("metric_value"), (int, float)):
        attrs["autolineage.metric_value"] = float(md["metric_value"])
    return {k: v for k, v in attrs.items() if v is not None and v != []}


class OTelExporter:
    """Handle returned by :func:`enable_otel_export`."""

    def __init__(self, tracker, tracer, run_name: str):
        trace = _require_otel()
        self._trace = trace
        self._tracker = tracker
        self._tracer = tracer
        self._run_span = tracer.start_span(run_name, attributes={"autolineage.version": _version()})
        self._run_ctx = trace.set_span_in_context(self._run_span)
        self._active = True
        self.spans_emitted = 0
        tracker.register_post_record_callback(self._on_record)

    def _on_record(self, rec) -> None:
        if not self._active:
            return
        end_ns = time.time_ns()
        start_ns = end_ns - int((rec.duration_ms or 0.0) * 1_000_000)
        name = f"{rec.library}.{rec.operation}" if rec.library else rec.operation
        span = self._tracer.start_span(
            name, context=self._run_ctx, start_time=start_ns,
            attributes=record_attributes(rec))
        span.end(end_time=end_ns)
        self.spans_emitted += 1

    def shutdown(self) -> None:
        """Stop exporting and end the ``autolineage.run`` span. Idempotent."""
        if not self._active:
            return
        self._active = False
        self._tracker.unregister_post_record_callback(self._on_record)
        self._run_span.set_attribute("autolineage.operations", self.spans_emitted)
        self._run_span.end()


def _version() -> str:
    try:
        from autolineage import __version__
        return str(__version__)
    except Exception:
        return "unknown"


def enable_otel_export(tracker=None, tracer_provider=None, *,
                       run_name: str = "autolineage.run") -> OTelExporter:
    """Export every operation the tracker records as an OpenTelemetry span.

    Args:
        tracker: the ``UnifiedTracker`` to export. Defaults to the global
            tracker started by ``import autolineage.auto``.
        tracer_provider: an OpenTelemetry ``TracerProvider``. Defaults to
            the global one (``opentelemetry.trace.get_tracer_provider()``);
            with no SDK configured that is a no-op provider and nothing is
            exported.
        run_name: name of the parent span that groups this run.

    Only operations recorded after this call are exported.
    """
    trace = _require_otel()
    if tracker is None:
        from autolineage.auto import get_tracker, start_tracking
        tracker = get_tracker() or start_tracking()
    provider = tracer_provider or trace.get_tracer_provider()
    tracer = provider.get_tracer("autolineage", _version())
    return OTelExporter(tracker, tracer, run_name)


__all__ = ["enable_otel_export", "OTelExporter", "record_attributes"]
