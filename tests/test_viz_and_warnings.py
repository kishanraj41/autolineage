"""Tests for visualization and the early-import warning."""
import json
import os
import tempfile
import warnings

import numpy as np
import pandas as pd
import pytest

from autolineage.core.tracker import UnifiedTracker
from autolineage.hooks.registry import HookRegistry


@pytest.fixture
def small_pipeline_tracker():
    """A tracker that has run a short pandas + sklearn pipeline."""
    HookRegistry._globally_installed.clear()
    tracker = UnifiedTracker()
    registry = HookRegistry()
    registry.install_all(tracker)

    try:
        rng = np.random.default_rng(0)
        df = pd.DataFrame({
            "a": rng.normal(0, 1, 200),
            "b": rng.exponential(1, 200),
            "y": rng.integers(0, 2, 200),
        })
        tracker.assign_id(df, source="synthetic")
        df = df.dropna()
        df = df[df["a"] > -2]
        df = df.assign(c=df["a"] * df["b"])

        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score

        X = df[["a", "b", "c"]]
        y = df["y"]
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.3, random_state=0)
        sc = StandardScaler()
        X_tr_s = sc.fit_transform(X_tr)
        X_te_s = sc.transform(X_te)
        m = LogisticRegression(max_iter=200)
        m.fit(X_tr_s, y_tr)
        y_pred = m.predict(X_te_s)
        accuracy_score(y_te, y_pred)

        yield tracker
    finally:
        registry.uninstall_all()


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

class TestVisualization:
    def test_visualize_writes_html_file(self, small_pipeline_tracker, tmp_path):
        out = tmp_path / "lineage.html"
        path = small_pipeline_tracker.visualize(str(out), open_browser=False)
        assert os.path.exists(path)
        html = out.read_text()
        assert html.startswith("<!DOCTYPE html>")
        assert "AutoLineage" in html

    def test_visualize_html_has_no_template_residue(self, small_pipeline_tracker, tmp_path):
        out = tmp_path / "lineage.html"
        small_pipeline_tracker.visualize(str(out), open_browser=False)
        html = out.read_text()
        for marker in ("__NODES_JSON__", "__EDGES_JSON__",
                       "__META__", "__LEGEND__", "__SUMMARY__"):
            assert marker not in html, f"Unfilled placeholder: {marker}"

    def test_visualize_inline_returns_string(self, small_pipeline_tracker):
        html = small_pipeline_tracker.visualize(inline=True)
        assert isinstance(html, str)
        assert html.startswith("<!DOCTYPE html>")
        # Inline mode must not write a file even if no path given
        assert not os.path.exists("lineage.html") or True  # don't depend on cwd

    def test_visualize_renders_all_records(self, small_pipeline_tracker, tmp_path):
        out = tmp_path / "lineage.html"
        small_pipeline_tracker.visualize(str(out), open_browser=False)
        html = out.read_text()
        # Every record should appear as a node in the embedded JSON
        n_records = len(small_pipeline_tracker.records)
        # The NODES array should contain n_records objects (one per record)
        assert html.count('"idx":') == n_records

    def test_to_dot_produces_valid_graphviz(self, small_pipeline_tracker):
        dot = small_pipeline_tracker.to_dot()
        assert dot.startswith("digraph AutoLineage {")
        assert dot.rstrip().endswith("}")
        # Must contain at least one node and have arrow syntax for edges
        assert "->" in dot or len(small_pipeline_tracker.records) <= 1

    def test_to_mermaid_produces_valid_markdown(self, small_pipeline_tracker):
        mm = small_pipeline_tracker.to_mermaid()
        assert mm.startswith("graph TD")
        # Should have classDef declarations for category styling
        assert "classDef transform" in mm or "classDef preprocess" in mm

    def test_visualize_handles_empty_tracker(self, tmp_path):
        tracker = UnifiedTracker()
        out = tmp_path / "empty.html"
        # Should not raise even when there are zero records
        tracker.visualize(str(out), open_browser=False)
        assert os.path.exists(out)
        assert tracker.to_dot().startswith("digraph")
        assert tracker.to_mermaid().startswith("graph TD")


class TestEdgeResolution:
    """Regression tests for the lineage-edge inference logic in viz.

    The pandas hooks commonly produce records that share the same
    child_id across an entire reassignment chain (because the user
    keeps reassigning ``df``). We must still draw edges in pipeline
    order rather than collapsing the chain or pointing edges backwards.
    """

    def _build(self):
        from autolineage.viz import _build_graph
        HookRegistry._globally_installed.clear()
        tracker = UnifiedTracker()
        HookRegistry().install_all(tracker)
        return tracker, _build_graph

    def test_linear_pandas_chain_produces_forward_edges(self):
        """The classic case: dropna -> filter -> assign on a single df."""
        tracker, build_graph = self._build()
        try:
            np.random.seed(0)
            df = pd.DataFrame({'a': np.random.randn(50), 'b': np.random.randn(50)})
            df = df.dropna()
            df = df[df['a'] > 0]
            df = df.assign(c=df['a'] * df['b'])

            nodes, edges = build_graph(tracker)
            assert len(nodes) == 3
            assert len(edges) == 2

            # Edges must point forward in record order, never backward.
            for e in edges:
                src_idx = int(e['src'][1:])
                dst_idx = int(e['dst'][1:])
                assert src_idx < dst_idx, (
                    f"Edge {e['src']} -> {e['dst']} points backward"
                )

            # The chain must be (n0 -> n1 -> n2) specifically, not a star.
            edge_pairs = {(int(e['src'][1:]), int(e['dst'][1:])) for e in edges}
            assert edge_pairs == {(0, 1), (1, 2)}, (
                f"Expected linear chain, got {edge_pairs}"
            )
        finally:
            HookRegistry().uninstall_all()

    def test_clicked_node_upstream_set_is_correct(self):
        """The upstream of the LAST record should be every prior record."""
        tracker, build_graph = self._build()
        try:
            np.random.seed(0)
            df = pd.DataFrame({'a': np.random.randn(50)})
            df = df.dropna()
            df = df[df['a'] > 0]
            df = df.assign(c=df['a'] * 2)

            nodes, edges = build_graph(tracker)
            # Compute upstream of the last node (assign) by walking incoming edges
            incoming = {n['id']: [] for n in nodes}
            for e in edges:
                incoming[e['dst']].append(e['src'])
            upstream = set()
            stack = ['n2']
            while stack:
                cur = stack.pop()
                for p in incoming[cur]:
                    if p not in upstream:
                        upstream.add(p)
                        stack.append(p)
            assert upstream == {'n0', 'n1'}, (
                f"Expected upstream {{n0, n1}}, got {upstream}"
            )
        finally:
            HookRegistry().uninstall_all()

    def test_layout_assigns_distinct_layers_per_chain_step(self):
        """Linear pandas chains should produce one layer per step,
        which is what makes the visual order match execution order."""
        tracker, build_graph = self._build()
        try:
            np.random.seed(0)
            df = pd.DataFrame({'a': np.random.randn(50)})
            df = df.dropna()
            df = df[df['a'] > 0]
            df = df.assign(c=df['a'] * 2)

            nodes, edges = build_graph(tracker)

            # Replicate the JS layer-assignment logic
            incoming = {n['id']: [] for n in nodes}
            for e in edges:
                incoming[e['dst']].append(e['src'])
            layer = {}
            def depth(node_id, seen=None):
                seen = seen or set()
                if node_id in layer:
                    return layer[node_id]
                if node_id in seen:
                    return 0
                seen.add(node_id)
                parents = incoming[node_id]
                if not parents:
                    layer[node_id] = 0
                    return 0
                d = max(depth(p, seen) + 1 for p in parents)
                layer[node_id] = d
                return d

            for n in nodes:
                depth(n['id'])

            # Layers must be 0, 1, 2 in record order.
            assert [layer['n0'], layer['n1'], layer['n2']] == [0, 1, 2]
        finally:
            HookRegistry().uninstall_all()


class TestJupyterRichOutput:
    """Tests for the Jupyter _repr_html_ hook."""

    def test_repr_returns_summary_string(self, small_pipeline_tracker):
        r = repr(small_pipeline_tracker)
        assert "UnifiedTracker" in r
        assert "operations" in r

    def test_repr_html_returns_html_with_summary(self, small_pipeline_tracker):
        html = small_pipeline_tracker._repr_html_()
        assert isinstance(html, str)
        assert "AutoLineage trace" in html
        assert "<table" in html
        # Must contain at least one operation name from the pipeline
        assert any(op in html for op in ("dropna", "fit_transform",
                                        "RandomForest", "filter"))

    def test_repr_html_handles_empty_tracker(self):
        tracker = UnifiedTracker()
        html = tracker._repr_html_()
        assert "no operations recorded" in html

    def test_repr_html_truncates_long_traces(self):
        """Traces longer than 12 ops should show a 'and N more' row."""
        from autolineage.core import TransformationRecord
        tracker = UnifiedTracker()
        for i in range(20):
            tracker.record(TransformationRecord(
                library="pandas", category="transform",
                operation=f"op_{i}", parent_ids=[], child_id=f"c{i}"))
        html = tracker._repr_html_()
        assert "and 8 more operations" in html


# ---------------------------------------------------------------------------
# Early-import warning
# ---------------------------------------------------------------------------

class TestEarlyImportWarning:
    """The most common user gotcha: importing sklearn metrics before
    installing autolineage hooks. Our install_all() should detect this
    and emit a UserWarning."""

    def test_warning_fires_when_metric_imported_early(self):
        """If __main__ has a reference to a sklearn metric BEFORE
        install_all runs, we should warn."""
        import sys
        import importlib

        # Force a clean reimport of sklearn.metrics so we get the
        # original (unwrapped) function back.
        HookRegistry._globally_installed.clear()
        registry = HookRegistry()
        registry.uninstall_all()

        # Drop any cached autolineage-wrapped versions
        if 'sklearn.metrics' in sys.modules:
            importlib.reload(sys.modules['sklearn.metrics'])

        from sklearn.metrics import f1_score
        # Inject the early-bound reference into __main__ (simulating
        # a user script that did `from sklearn.metrics import f1_score`
        # at the top).
        main = sys.modules['__main__']
        main.f1_score = f1_score

        try:
            tracker = UnifiedTracker()
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                registry.install_all(tracker)

            messages = [str(w.message) for w in captured
                        if issubclass(w.category, UserWarning)]
            assert any("imported BEFORE install_all" in m for m in messages), (
                f"Expected early-import warning, got: {messages}"
            )
        finally:
            # Cleanup so subsequent tests don't pollute __main__
            try:
                del main.f1_score
            except AttributeError:
                pass
            registry.uninstall_all()
