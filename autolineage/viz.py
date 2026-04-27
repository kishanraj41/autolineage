"""
Lineage visualization.

Produces interactive HTML, Graphviz DOT, and Mermaid output for the
lineage DAG. Zero external runtime dependencies — the HTML output is
self-contained and works in Jupyter, browsers, and arbitrary file
systems without requiring Graphviz, networkx, or any plotting library
to be installed.

Public API::

    from autolineage.viz import visualize, to_dot, to_mermaid

    visualize(tracker)                       # write & open lineage.html
    visualize(tracker, output="trace.html")  # specify output path
    visualize(tracker, inline=True)          # return HTML string for Jupyter
    print(to_dot(tracker))                   # Graphviz DOT
    print(to_mermaid(tracker))               # Mermaid for Markdown
"""

from __future__ import annotations

import json
import os
import webbrowser
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple


# ---------------------------------------------------------------------------
# Color palette per category. Used by all three exporters so the visual
# encoding stays consistent across HTML / DOT / Mermaid.
# ---------------------------------------------------------------------------
_CATEGORY_COLORS: Dict[str, Tuple[str, str]] = {
    # category -> (fill, border)
    "io":         ("#fff4cc", "#caa400"),
    "transform":  ("#cfe2ff", "#3a76d8"),
    "split":      ("#ffd9b3", "#cc6f00"),
    "preprocess": ("#e6d6ff", "#6f42c1"),
    "train":      ("#c8f0c8", "#2c8a2c"),
    "predict":    ("#cdf0ee", "#137a72"),
    "evaluate":   ("#ffd1d1", "#b02020"),
    "action":     ("#dee2e6", "#666666"),
    "unknown":    ("#f0f0f0", "#999999"),
}


def _category_for(rec) -> str:
    cat = (getattr(rec, "category", None) or "unknown").lower()
    return cat if cat in _CATEGORY_COLORS else "unknown"


def _shape_label(rec) -> str:
    """One-line shape annotation: input -> output, or just output."""
    inp = getattr(rec, "input_shape", None)
    out = getattr(rec, "output_shape", None)
    if inp and out and inp != out:
        return f"{tuple(inp)} \u2192 {tuple(out)}"
    if out:
        return f"{tuple(out)}"
    if inp:
        return f"{tuple(inp)}"
    return ""


def _node_label(idx: int, rec) -> str:
    op = getattr(rec, "operation", "?")
    return f"{idx + 1}. {op}"


def _node_subtitle(rec) -> str:
    parts: List[str] = []
    shape = _shape_label(rec)
    if shape:
        parts.append(shape)
    rb = getattr(rec, "rows_before", None)
    ra = getattr(rec, "rows_after", None)
    if rb is not None and ra is not None and rb != ra:
        delta = ra - rb
        parts.append(f"{delta:+,d} rows")
    md = getattr(rec, "metadata", None) or {}
    if md.get("metric_value") is not None:
        try:
            parts.append(f"= {md['metric_value']:.4f}")
        except Exception:
            pass
    dur = getattr(rec, "duration_ms", None)
    if dur is not None and dur > 0:
        parts.append(f"{dur:.0f}ms")
    return " \u00b7 ".join(parts)


def _build_graph(tracker) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Translate tracker.records into renderable node/edge lists.

    Strategy: each TransformationRecord becomes one node. Edges are
    drawn from each parent_id node to the record's own node. Records
    without a matching parent record (e.g. read_csv with a file source)
    are root nodes.

    Edge resolution handles two complications:
      1. Pandas reassignment chains often produce the same child_id for
         every operation (because the user keeps reassigning ``df``).
         A naive child_id->index map gets clobbered, so we instead map
         child_id to the *list* of indices that produced it and walk it
         forward-in-time only.
      2. Records may have no parent_ids (e.g. a freshly constructed
         DataFrame that bypassed the I/O hooks). For these we fall
         back to the immediately preceding record on the same library
         track, which is correct for linear chains and only mildly
         pessimistic for branching ones.
    """
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    # Map child_id -> ALL indices that produced it (in chronological order).
    # Pandas reassignment chains commonly reuse a single id for every step.
    child_to_indices: Dict[str, List[int]] = {}
    for i, rec in enumerate(tracker.records):
        cid = getattr(rec, "child_id", None)
        if cid is not None:
            child_to_indices.setdefault(cid, []).append(i)

    for i, rec in enumerate(tracker.records):
        cat = _category_for(rec)
        fill, border = _CATEGORY_COLORS[cat]
        nodes.append({
            "idx": i,
            "id": f"n{i}",
            "label": _node_label(i, rec),
            "subtitle": _node_subtitle(rec),
            "category": cat,
            "library": getattr(rec, "library", "") or "",
            "operation": getattr(rec, "operation", "") or "",
            "fill": fill,
            "border": border,
            "duration_ms": getattr(rec, "duration_ms", None),
            "input_shape": getattr(rec, "input_shape", None),
            "output_shape": getattr(rec, "output_shape", None),
            "rows_before": getattr(rec, "rows_before", None),
            "rows_after": getattr(rec, "rows_after", None),
            "metric_value": (getattr(rec, "metadata", {}) or {}).get("metric_value"),
        })

        # Resolve incoming edges. For each parent_id, pick the most recent
        # record (strictly before i) that produced that id. This handles
        # the pandas reassignment-chain case correctly.
        added_edge = False
        for pid in (getattr(rec, "parent_ids", None) or []):
            candidates = [j for j in child_to_indices.get(pid, []) if j < i]
            if candidates:
                edges.append({"src": f"n{candidates[-1]}", "dst": f"n{i}"})
                added_edge = True

        # Fallback: if no parent edge was resolved AND this isn't the
        # first record, draw an edge from the previous record on the
        # same library. Catches synthetic-DataFrame pipelines that
        # never went through a hooked I/O operation.
        if not added_edge and i > 0:
            prev = tracker.records[i - 1]
            same_lib = (getattr(prev, "library", None)
                        == getattr(rec, "library", None))
            if same_lib:
                edges.append({"src": f"n{i-1}", "dst": f"n{i}"})

    return nodes, edges


# ---------------------------------------------------------------------------
# DOT (Graphviz)
# ---------------------------------------------------------------------------

def to_dot(tracker, *, rankdir: str = "TB") -> str:
    """Return the lineage graph in Graphviz DOT format."""
    nodes, edges = _build_graph(tracker)
    out: List[str] = []
    out.append("digraph AutoLineage {")
    out.append(f'  rankdir={rankdir};')
    out.append('  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10];')
    out.append('  edge [color="#888888"];')

    for n in nodes:
        label = n["label"]
        sub = n["subtitle"]
        if sub:
            label = f"{label}\\n{sub}"
        # DOT requires escaping double quotes in labels
        label = label.replace('"', '\\"')
        out.append(
            f'  {n["id"]} [label="{label}", fillcolor="{n["fill"]}", '
            f'color="{n["border"]}"];'
        )

    for e in edges:
        out.append(f'  {e["src"]} -> {e["dst"]};')
    out.append("}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Mermaid (good for Markdown, GitHub READMEs, blog posts)
# ---------------------------------------------------------------------------

def to_mermaid(tracker) -> str:
    nodes, edges = _build_graph(tracker)
    out: List[str] = []
    out.append("graph TD")
    for n in nodes:
        label = n["label"]
        sub = n["subtitle"]
        if sub:
            label = f"{label}<br/>{sub}"
        # Mermaid doesn't allow some characters in raw labels — wrap in quotes.
        label_safe = label.replace('"', "&quot;")
        out.append(f'  {n["id"]}["{label_safe}"]')

    for e in edges:
        out.append(f'  {e["src"]} --> {e["dst"]}')

    # Style classes per category
    for cat, (fill, border) in _CATEGORY_COLORS.items():
        out.append(f"  classDef {cat} fill:{fill},stroke:{border},color:#222;")
    for n in nodes:
        out.append(f'  class {n["id"]} {n["category"]};')
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Standalone HTML (no external dependencies, no CDN required for the layout)
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AutoLineage Trace</title>
<style>
  :root {
    --bg: #fafafa;
    --panel: #ffffff;
    --text: #1a1a1a;
    --muted: #666;
    --border: #e0e0e0;
    --accent: #2c5282;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg); color: var(--text);
  }
  header {
    padding: 18px 24px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; gap: 24px;
  }
  header h1 {
    font-size: 18px; font-weight: 600; margin: 0;
  }
  header .meta {
    font-size: 13px; color: var(--muted);
  }
  .legend {
    display: flex; gap: 12px; flex-wrap: wrap; font-size: 12px;
    margin-left: auto;
  }
  .legend-item { display: flex; align-items: center; gap: 6px; }
  .legend-swatch {
    width: 14px; height: 14px; border-radius: 3px; border: 1px solid;
  }
  main {
    display: grid;
    grid-template-columns: 1fr 320px;
    gap: 0;
    height: calc(100vh - 64px);
  }
  #graph { background: var(--bg); position: relative; overflow: hidden; }
  #graph svg { width: 100%; height: 100%; cursor: grab; }
  #graph svg.dragging { cursor: grabbing; }
  .node-rect {
    rx: 6; ry: 6;
    stroke-width: 1.5;
    cursor: pointer;
    transition: filter 120ms ease;
  }
  .node-rect:hover { filter: brightness(0.95); }
  .node-rect.selected {
    stroke-width: 3;
    filter: drop-shadow(0 0 6px rgba(0,0,0,0.25));
  }
  .node-rect.upstream { stroke-dasharray: 4 2; }
  .node-label {
    font-size: 11px; font-weight: 600;
    pointer-events: none; user-select: none;
  }
  .node-sub {
    font-size: 10px; fill: #444; pointer-events: none; user-select: none;
  }
  .edge {
    stroke: #888; stroke-width: 1.2; fill: none;
  }
  .edge.highlighted { stroke: var(--accent); stroke-width: 2.2; }
  aside {
    background: var(--panel);
    border-left: 1px solid var(--border);
    padding: 18px;
    overflow-y: auto;
  }
  aside h2 {
    font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;
    color: var(--muted); margin: 0 0 12px;
  }
  .kv { font-size: 13px; margin: 6px 0; }
  .kv b { display: inline-block; min-width: 100px; color: var(--muted); font-weight: 500; }
  .empty { color: var(--muted); font-style: italic; font-size: 13px; }
  .controls {
    position: absolute; top: 12px; left: 12px;
    display: flex; gap: 4px; background: var(--panel);
    border: 1px solid var(--border); border-radius: 6px;
    padding: 4px;
  }
  .controls button {
    border: none; background: transparent; padding: 6px 10px;
    cursor: pointer; font-size: 13px; border-radius: 4px;
    color: var(--text);
  }
  .controls button:hover { background: var(--bg); }
  .summary-bar {
    padding: 10px 16px; font-size: 13px; color: var(--muted);
    background: var(--panel); border-bottom: 1px solid var(--border);
  }
  .summary-bar b { color: var(--text); }
</style>
</head>
<body>
<header>
  <h1>AutoLineage</h1>
  <div class="meta">__META__</div>
  <div class="legend">__LEGEND__</div>
</header>
<div class="summary-bar">__SUMMARY__</div>
<main>
  <div id="graph">
    <div class="controls">
      <button id="zoom-in">+</button>
      <button id="zoom-out">&minus;</button>
      <button id="reset">Reset</button>
    </div>
    <svg id="svg" xmlns="http://www.w3.org/2000/svg"></svg>
  </div>
  <aside>
    <h2>Selected operation</h2>
    <div id="detail" class="empty">Click a node to inspect</div>
  </aside>
</main>
<script>
const NODES = __NODES_JSON__;
const EDGES = __EDGES_JSON__;

// ---------------------------------------------------------------------
// Layered (Sugiyama-lite) layout. Pure JS, no dependencies.
// ---------------------------------------------------------------------
function layout(nodes, edges) {
  const byId = new Map(nodes.map(n => [n.id, n]));
  const incoming = new Map(nodes.map(n => [n.id, []]));
  const outgoing = new Map(nodes.map(n => [n.id, []]));
  for (const e of edges) {
    if (!byId.has(e.src) || !byId.has(e.dst)) continue;
    incoming.get(e.dst).push(e.src);
    outgoing.get(e.src).push(e.dst);
  }
  // Layer assignment via longest-path from sources.
  const layer = new Map();
  function depth(id, seen) {
    if (layer.has(id)) return layer.get(id);
    if (seen.has(id)) return 0;
    seen.add(id);
    const parents = incoming.get(id);
    if (!parents.length) { layer.set(id, 0); return 0; }
    let d = 0;
    for (const p of parents) d = Math.max(d, depth(p, seen) + 1);
    layer.set(id, d);
    return d;
  }
  for (const n of nodes) depth(n.id, new Set());

  const layers = [];
  for (const [id, l] of layer.entries()) {
    while (layers.length <= l) layers.push([]);
    layers[l].push(id);
  }

  // Position: x = layer index, y = order within layer
  // Use record index to keep ordering stable.
  for (const lyr of layers) lyr.sort((a, b) => byId.get(a).idx - byId.get(b).idx);

  const NODE_W = 200, NODE_H = 56;
  const X_GAP = 80, Y_GAP = 24;
  const positions = new Map();
  for (let li = 0; li < layers.length; li++) {
    const lyr = layers[li];
    const totalH = lyr.length * NODE_H + (lyr.length - 1) * Y_GAP;
    const startY = -totalH / 2 + NODE_H / 2;
    for (let i = 0; i < lyr.length; i++) {
      positions.set(lyr[i], {
        x: li * (NODE_W + X_GAP),
        y: startY + i * (NODE_H + Y_GAP),
      });
    }
  }
  return { positions, NODE_W, NODE_H };
}

const { positions, NODE_W, NODE_H } = layout(NODES, EDGES);

// ---------------------------------------------------------------------
// Render SVG
// ---------------------------------------------------------------------
const svg = document.getElementById('svg');
const NS = 'http://www.w3.org/2000/svg';

// One root group for pan/zoom transforms.
const root = document.createElementNS(NS, 'g');
svg.appendChild(root);

// Edges first so they sit underneath nodes.
const edgeGroup = document.createElementNS(NS, 'g');
root.appendChild(edgeGroup);

const edgeElems = [];
for (const e of EDGES) {
  const ps = positions.get(e.src), pd = positions.get(e.dst);
  if (!ps || !pd) continue;
  const x1 = ps.x + NODE_W / 2, y1 = ps.y;
  const x2 = pd.x - NODE_W / 2, y2 = pd.y;
  const mx = (x1 + x2) / 2;
  const path = document.createElementNS(NS, 'path');
  path.setAttribute('d', `M ${x1} ${y1} C ${mx} ${y1} ${mx} ${y2} ${x2} ${y2}`);
  path.setAttribute('class', 'edge');
  path.dataset.src = e.src; path.dataset.dst = e.dst;
  edgeGroup.appendChild(path);
  edgeElems.push(path);
}

const nodeGroup = document.createElementNS(NS, 'g');
root.appendChild(nodeGroup);

const nodeElems = new Map();
for (const n of NODES) {
  const p = positions.get(n.id);
  const g = document.createElementNS(NS, 'g');
  g.setAttribute('transform', `translate(${p.x - NODE_W / 2} ${p.y - NODE_H / 2})`);
  g.style.cursor = 'pointer';

  const rect = document.createElementNS(NS, 'rect');
  rect.setAttribute('width', NODE_W);
  rect.setAttribute('height', NODE_H);
  rect.setAttribute('class', 'node-rect');
  rect.setAttribute('fill', n.fill);
  rect.setAttribute('stroke', n.border);
  g.appendChild(rect);

  const t1 = document.createElementNS(NS, 'text');
  t1.setAttribute('x', NODE_W / 2);
  t1.setAttribute('y', 22);
  t1.setAttribute('text-anchor', 'middle');
  t1.setAttribute('class', 'node-label');
  t1.textContent = n.label.length > 30 ? n.label.slice(0, 28) + '...' : n.label;
  g.appendChild(t1);

  if (n.subtitle) {
    const t2 = document.createElementNS(NS, 'text');
    t2.setAttribute('x', NODE_W / 2);
    t2.setAttribute('y', 40);
    t2.setAttribute('text-anchor', 'middle');
    t2.setAttribute('class', 'node-sub');
    t2.textContent = n.subtitle.length > 38 ? n.subtitle.slice(0, 36) + '...' : n.subtitle;
    g.appendChild(t2);
  }

  g.addEventListener('click', (ev) => { ev.stopPropagation(); selectNode(n.id); });
  nodeGroup.appendChild(g);
  nodeElems.set(n.id, { group: g, rect });
}

// Set viewBox to fit content.
function fitView() {
  const bbox = root.getBBox();
  const pad = 40;
  svg.setAttribute('viewBox',
    `${bbox.x - pad} ${bbox.y - pad} ${bbox.width + 2*pad} ${bbox.height + 2*pad}`);
}
requestAnimationFrame(fitView);

// ---------------------------------------------------------------------
// Selection / upstream highlighting
// ---------------------------------------------------------------------
function ancestors(id) {
  const result = new Set();
  const stack = [id];
  const incoming = new Map(NODES.map(n => [n.id, []]));
  for (const e of EDGES) incoming.get(e.dst).push(e.src);
  while (stack.length) {
    const cur = stack.pop();
    for (const p of incoming.get(cur) || []) {
      if (!result.has(p)) { result.add(p); stack.push(p); }
    }
  }
  return result;
}

function selectNode(id) {
  for (const [, info] of nodeElems) info.rect.classList.remove('selected', 'upstream');
  for (const e of edgeElems) e.classList.remove('highlighted');

  const sel = nodeElems.get(id); if (!sel) return;
  sel.rect.classList.add('selected');

  const anc = ancestors(id);
  for (const aId of anc) {
    const info = nodeElems.get(aId); if (info) info.rect.classList.add('upstream');
  }
  for (const e of edgeElems) {
    if ((e.dataset.dst === id || anc.has(e.dataset.dst)) && (e.dataset.src === id || anc.has(e.dataset.src) || e.dataset.dst === id)) {
      e.classList.add('highlighted');
    }
  }

  const node = NODES.find(n => n.id === id);
  const detail = document.getElementById('detail');
  detail.classList.remove('empty');
  const rows = [];
  rows.push(`<div class="kv"><b>Operation</b>${node.operation}</div>`);
  rows.push(`<div class="kv"><b>Library</b>${node.library || '—'}</div>`);
  rows.push(`<div class="kv"><b>Category</b>${node.category}</div>`);
  if (node.input_shape)  rows.push(`<div class="kv"><b>Input shape</b>${JSON.stringify(node.input_shape)}</div>`);
  if (node.output_shape) rows.push(`<div class="kv"><b>Output shape</b>${JSON.stringify(node.output_shape)}</div>`);
  if (node.rows_before != null && node.rows_after != null) {
    const d = node.rows_after - node.rows_before;
    rows.push(`<div class="kv"><b>Rows</b>${node.rows_before.toLocaleString()} \u2192 ${node.rows_after.toLocaleString()} (${d>=0?'+':''}${d.toLocaleString()})</div>`);
  }
  if (node.duration_ms != null) rows.push(`<div class="kv"><b>Duration</b>${node.duration_ms.toFixed(1)} ms</div>`);
  if (node.metric_value != null) rows.push(`<div class="kv"><b>Metric value</b>${node.metric_value.toFixed(4)}</div>`);
  rows.push(`<div class="kv"><b>Upstream</b>${anc.size} operations</div>`);
  detail.innerHTML = rows.join('');
}
svg.addEventListener('click', () => {
  for (const [, info] of nodeElems) info.rect.classList.remove('selected', 'upstream');
  for (const e of edgeElems) e.classList.remove('highlighted');
  document.getElementById('detail').className = 'empty';
  document.getElementById('detail').textContent = 'Click a node to inspect';
});

// ---------------------------------------------------------------------
// Pan & zoom
// ---------------------------------------------------------------------
let viewBox = null;
function getVB() {
  return svg.getAttribute('viewBox').split(/\s+/).map(parseFloat);
}
function setVB(vb) { svg.setAttribute('viewBox', vb.join(' ')); }

let dragStart = null;
svg.addEventListener('mousedown', e => {
  dragStart = { x: e.clientX, y: e.clientY, vb: getVB() };
  svg.classList.add('dragging');
});
window.addEventListener('mousemove', e => {
  if (!dragStart) return;
  const [x, y, w, h] = dragStart.vb;
  const rect = svg.getBoundingClientRect();
  const sx = w / rect.width, sy = h / rect.height;
  setVB([ x - (e.clientX - dragStart.x) * sx, y - (e.clientY - dragStart.y) * sy, w, h ]);
});
window.addEventListener('mouseup', () => { dragStart = null; svg.classList.remove('dragging'); });
svg.addEventListener('wheel', e => {
  e.preventDefault();
  const [x, y, w, h] = getVB();
  const factor = e.deltaY < 0 ? 0.9 : 1.1;
  const rect = svg.getBoundingClientRect();
  const mx = x + (e.clientX - rect.left) / rect.width * w;
  const my = y + (e.clientY - rect.top) / rect.height * h;
  const nw = w * factor, nh = h * factor;
  setVB([ mx - (mx - x) * factor, my - (my - y) * factor, nw, nh ]);
}, { passive: false });

document.getElementById('zoom-in').onclick = () => {
  const [x, y, w, h] = getVB(); const nw = w * 0.8, nh = h * 0.8;
  setVB([x + (w - nw)/2, y + (h - nh)/2, nw, nh]);
};
document.getElementById('zoom-out').onclick = () => {
  const [x, y, w, h] = getVB(); const nw = w * 1.25, nh = h * 1.25;
  setVB([x + (w - nw)/2, y + (h - nh)/2, nw, nh]);
};
document.getElementById('reset').onclick = fitView;
</script>
</body>
</html>
"""


def _build_html(tracker, *, title: str = "") -> str:
    nodes, edges = _build_graph(tracker)
    summary = tracker.get_summary() if hasattr(tracker, "get_summary") else {}
    libs = summary.get("libraries_tracked") or []

    meta_parts: List[str] = []
    meta_parts.append(datetime.now().strftime("%Y-%m-%d %H:%M"))
    meta_parts.append(f"{len(nodes)} operations")
    if libs:
        meta_parts.append("/".join(libs))
    meta = " &middot; ".join(meta_parts)

    # Legend = the categories actually present in this trace.
    present_cats: List[str] = []
    seen: set = set()
    for n in nodes:
        if n["category"] not in seen:
            seen.add(n["category"])
            present_cats.append(n["category"])
    legend_html = "".join(
        f'<div class="legend-item">'
        f'<span class="legend-swatch" style="background:{_CATEGORY_COLORS[c][0]};'
        f'border-color:{_CATEGORY_COLORS[c][1]};"></span>{c}</div>'
        for c in present_cats
    )

    # One-line summary across libraries.
    parts: List[str] = []
    rows_filt = summary.get("total_rows_filtered")
    cols_chg = summary.get("total_column_changes")
    if rows_filt:
        parts.append(f"<b>{rows_filt:,}</b> rows filtered")
    if cols_chg:
        parts.append(f"<b>{cols_chg}</b> column changes")
    by_lib = summary.get("by_library", {})
    if by_lib:
        lib_counts = []
        for lib, ops in by_lib.items():
            total = sum(ops.values())
            lib_counts.append(f"<b>{total}</b> {lib}")
        parts.append(" / ".join(lib_counts))
    summary_html = " &nbsp;&middot;&nbsp; ".join(parts) if parts else "&nbsp;"

    html = (_HTML_TEMPLATE
            .replace("__NODES_JSON__", json.dumps(nodes, default=str))
            .replace("__EDGES_JSON__", json.dumps(edges))
            .replace("__META__", meta)
            .replace("__LEGEND__", legend_html)
            .replace("__SUMMARY__", summary_html))
    return html


def visualize(tracker, output: Optional[str] = None, *,
              inline: bool = False, open_browser: bool = True,
              title: str = "") -> Optional[str]:
    """Render the lineage DAG as an interactive HTML page.

    Parameters
    ----------
    tracker : UnifiedTracker
        The tracker whose records should be visualized.
    output : str, optional
        Path to write the HTML file. Defaults to ``./lineage.html``.
        Ignored when ``inline=True``.
    inline : bool, default False
        If True, return the HTML as a string (suitable for
        IPython.display.HTML). If False, write to disk.
    open_browser : bool, default True
        If True and writing to disk, open the file in a browser.
    title : str, optional
        Optional human title shown in the page header (currently unused
        in the template; kept for forward compatibility).

    Returns
    -------
    str
        Either the HTML string (inline=True) or the absolute path of
        the written file.
    """
    html = _build_html(tracker, title=title)

    if inline:
        return html

    output = output or "lineage.html"
    output = os.path.abspath(output)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(html)

    if open_browser:
        try:
            webbrowser.open(f"file://{output}")
        except Exception:
            pass
    return output


# ---------------------------------------------------------------------------
# Jupyter convenience
# ---------------------------------------------------------------------------

def to_jupyter(tracker):
    """Return an IPython.display.HTML object for inline notebook display.

    Lazy imports IPython so the rest of the module works without it.
    """
    try:
        from IPython.display import HTML  # noqa
    except ImportError:
        raise RuntimeError("IPython is not installed; install autolineage[jupyter]")
    return HTML(_build_html(tracker))
