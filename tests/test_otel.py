"""OpenTelemetry export (autolineage[otel] extra)."""

import pandas as pd
import pytest

pytest.importorskip("opentelemetry.sdk")

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from autolineage.core import TransformationRecord
from autolineage.core.tracker import UnifiedTracker
from autolineage.hooks.registry import HookRegistry
from autolineage.otel import enable_otel_export, record_attributes


@pytest.fixture
def otel():
    """A private tracer provider with an in-memory exporter (never the
    global provider, so tests don't leak into each other)."""
    mem = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(mem))
    return provider, mem


@pytest.fixture
def hooked():
    HookRegistry._globally_installed.clear()
    tracker = UnifiedTracker()
    reg = HookRegistry()
    reg.install_all(tracker)
    yield tracker
    reg.uninstall_all()
    HookRegistry._globally_installed.clear()


def _spans(mem):
    return {s.name: s for s in mem.get_finished_spans()}


def test_each_operation_becomes_a_span_under_one_run(hooked, otel):
    provider, mem = otel
    exp = enable_otel_export(hooked, provider)
    df = pd.DataFrame({"k": [1, 2, 3], "v": [1.0, None, 3.0]})
    df = df.dropna()
    df = df.merge(pd.DataFrame({"k": [1, 3], "w": [5, 6]}), on="k")
    exp.shutdown()

    spans = mem.get_finished_spans()
    run = [s for s in spans if s.name == "autolineage.run"]
    ops = [s for s in spans if s.name != "autolineage.run"]
    assert len(run) == 1
    assert [s.name for s in ops] == ["pandas-transforms.dropna", "pandas-transforms.merge"]
    assert all(s.parent.span_id == run[0].context.span_id for s in ops)
    assert all(s.context.trace_id == run[0].context.trace_id for s in ops)
    assert run[0].attributes["autolineage.operations"] == 2


def test_span_attributes_carry_lineage_and_shape(hooked, otel):
    provider, mem = otel
    exp = enable_otel_export(hooked, provider)
    df = pd.DataFrame({"a": [1, 2, 3, 4]})
    out = df[df["a"] > 2]
    exp.shutdown()

    span = _spans(mem)["pandas-transforms.filter"]
    a = span.attributes
    assert a["autolineage.operation"] == "filter"
    assert a["autolineage.rows_before"] == 4 and a["autolineage.rows_after"] == 2
    assert a["autolineage.row_delta"] == -2
    assert tuple(a["autolineage.parent_ids"]) == (hooked.get_id(df),)
    assert a["autolineage.child_id"] == hooked.get_id(out)
    assert tuple(a["autolineage.output_shape"]) == (2, 1)
    assert span.end_time >= span.start_time


def test_metric_value_exported(hooked, otel):
    from sklearn.metrics import f1_score   # imported after install: hooked
    provider, mem = otel
    exp = enable_otel_export(hooked, provider)
    f1_score([0, 1, 1], [0, 1, 0])
    exp.shutdown()
    a = _spans(mem)["sklearn.f1_score"].attributes
    assert a["autolineage.metric_name"] == "f1_score"
    assert a["autolineage.metric_value"] == pytest.approx(2 / 3)


def test_shutdown_stops_export_and_is_idempotent(hooked, otel):
    provider, mem = otel
    exp = enable_otel_export(hooked, provider)
    pd.DataFrame({"a": [1, None]}).dropna()
    exp.shutdown()
    exp.shutdown()
    n = len(mem.get_finished_spans())
    pd.DataFrame({"a": [1, None]}).dropna()     # after shutdown
    assert len(mem.get_finished_spans()) == n
    assert exp._on_record not in hooked._post_record_callbacks


def test_only_operations_after_enable_are_exported(hooked, otel):
    provider, mem = otel
    pd.DataFrame({"a": [1, None]}).dropna()     # before enable
    exp = enable_otel_export(hooked, provider)
    exp.shutdown()
    assert [s.name for s in mem.get_finished_spans()] == ["autolineage.run"]


def test_wide_column_lists_are_capped():
    rec = TransformationRecord(library="pandas-transforms", operation="get_dummies",
                               columns_added=[f"c{i}" for i in range(400)])
    a = record_attributes(rec)
    assert len(a["autolineage.columns_added"]) == 50
    assert a["autolineage.columns_added_count"] == 400


def test_attributes_are_otel_valid_types():
    rec = TransformationRecord(library="sklearn", category="evaluate", operation="f1_score",
                               parent_ids=["", "abc"], input_shape=(3, 2),
                               metadata={"metric_name": "f1_score", "metric_value": 0.5})
    a = record_attributes(rec)
    for v in a.values():
        assert isinstance(v, (str, bool, int, float, list))
        if isinstance(v, list):
            assert len({type(x) for x in v}) <= 1
    assert a["autolineage.parent_ids"] == ["abc"]          # empty IDs dropped
    assert "autolineage.rows_before" not in a              # None fields omitted


def test_unregister_post_record_callback():
    t = UnifiedTracker()
    seen = []
    cb = seen.append
    t.register_post_record_callback(cb)
    t.record(TransformationRecord(operation="x"))
    assert t.unregister_post_record_callback(cb) is True
    assert t.unregister_post_record_callback(cb) is False
    t.record(TransformationRecord(operation="y"))
    assert [r.operation for r in seen] == ["x"]
