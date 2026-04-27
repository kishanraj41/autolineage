"""
Unified lineage tracker.

All hook providers feed into this single tracker. One DAG regardless
of whether the operation came from pandas, sklearn, or PySpark.
"""

import uuid
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from weakref import WeakValueDictionary

from . import TransformationRecord


class UnifiedTracker:
    """Central lineage tracker that all hook providers write to."""

    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.records: List[TransformationRecord] = []
        self._id_to_lid: Dict[int, str] = {}
        self._lid_to_obj: WeakValueDictionary = WeakValueDictionary()
        self._file_to_lid: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Lineage-ID management
    # ------------------------------------------------------------------

    def assign_id(self, obj, *, source: str = "unknown",
                  filepath: str = None) -> str:
        lid = str(uuid.uuid4())[:12]

        if hasattr(obj, 'attrs') and isinstance(getattr(obj, 'attrs', None), dict):
            obj.attrs['_lineage_id'] = lid
        else:
            self._id_to_lid[id(obj)] = lid
            try:
                self._lid_to_obj[lid] = obj
            except TypeError:
                pass

        shape = None
        columns = None
        if hasattr(obj, 'shape'):
            try:
                shape = tuple(obj.shape)
            except Exception:
                pass
        if hasattr(obj, 'columns'):
            try:
                columns = list(obj.columns)
            except Exception:
                pass

        self.nodes[lid] = {
            'id': lid,
            'source': source,
            'filepath': filepath,
            'shape': shape,
            'columns': columns,
            'content_hash': self._hash(obj),
            'created_at': datetime.now().isoformat(),
        }

        if filepath:
            self._file_to_lid[filepath] = lid

        return lid

    def get_id(self, obj) -> Optional[str]:
        if hasattr(obj, 'attrs') and isinstance(getattr(obj, 'attrs', None), dict):
            lid = obj.attrs.get('_lineage_id')
            if lid:
                return lid
        return self._id_to_lid.get(id(obj))

    def get_or_assign(self, obj, **kwargs) -> str:
        lid = self.get_id(obj)
        if lid is None:
            lid = self.assign_id(obj, **kwargs)
        return lid

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, rec: TransformationRecord) -> None:
        self.records.append(rec)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_chain(self, lid: str) -> List[TransformationRecord]:
        chain: List[TransformationRecord] = []
        visited: set = set()
        self._walk_back(lid, chain, visited)
        return list(reversed(chain))

    def _walk_back(self, lid, chain, visited):
        if lid in visited:
            return
        visited.add(lid)
        for rec in self.records:
            if rec.child_id == lid:
                chain.append(rec)
                for pid in rec.parent_ids:
                    self._walk_back(pid, chain, visited)

    def get_summary(self) -> Dict[str, Any]:
        by_library: Dict[str, Dict[str, int]] = {}
        total_rows_removed = 0
        total_cols_changed = 0

        for rec in self.records:
            lib = rec.library or "unknown"
            if lib not in by_library:
                by_library[lib] = {}
            op = rec.operation
            by_library[lib][op] = by_library[lib].get(op, 0) + 1

            if rec.rows_before is not None and rec.rows_after is not None:
                diff = rec.rows_before - rec.rows_after
                if diff > 0:
                    total_rows_removed += diff
            if rec.columns_added:
                total_cols_changed += len(rec.columns_added)
            if rec.columns_removed:
                total_cols_changed += len(rec.columns_removed)

        return {
            'total_records': len(self.records),
            'total_nodes': len(self.nodes),
            'by_library': by_library,
            'total_rows_filtered': total_rows_removed,
            'total_column_changes': total_cols_changed,
            'libraries_tracked': sorted(by_library.keys()),
        }

    def get_full_graph(self) -> Dict[str, Any]:
        return {
            'nodes': self.nodes,
            'edges': [r.to_dict() for r in self.records],
            'file_mappings': self._file_to_lid,
        }

    def get_timing_profile(self) -> List[Dict[str, Any]]:
        """Return operations sorted by duration (slowest first).

        Useful for identifying pipeline bottlenecks.

        Returns
        -------
        List of dicts with keys: operation, library, category,
        duration_ms, percent_of_total.
        """
        timed = [(r, r.duration_ms) for r in self.records
                 if r.duration_ms is not None and r.duration_ms > 0]
        if not timed:
            return []

        total_ms = sum(d for _, d in timed)
        timed.sort(key=lambda x: x[1], reverse=True)

        return [
            {
                'operation': r.operation,
                'library': r.library,
                'category': r.category,
                'duration_ms': round(d, 2),
                'percent_of_total': round(d / total_ms * 100, 1) if total_ms > 0 else 0,
            }
            for r, d in timed
        ]

    # ------------------------------------------------------------------
    # Visualization (delegates to autolineage.viz)
    # ------------------------------------------------------------------

    def visualize(self, output: Optional[str] = None, *,
                  inline: bool = False, open_browser: bool = True):
        """Render the captured lineage as an interactive HTML page.

        See :func:`autolineage.viz.visualize` for full parameter docs.
        Quick usage::

            tracker.visualize()                     # writes ./lineage.html
            tracker.visualize("trace.html")         # custom path
            tracker.visualize(inline=True)          # returns HTML string

        In Jupyter notebooks, use ``IPython.display.HTML(tracker.visualize(inline=True))``
        or the convenience helper ``autolineage.viz.to_jupyter(tracker)``.
        """
        from ..viz import visualize as _visualize
        return _visualize(self, output=output, inline=inline,
                          open_browser=open_browser)

    def to_dot(self, *, rankdir: str = "TB") -> str:
        """Return the lineage DAG in Graphviz DOT format."""
        from ..viz import to_dot as _to_dot
        return _to_dot(self, rankdir=rankdir)

    def to_mermaid(self) -> str:
        """Return the lineage DAG in Mermaid format (for Markdown/READMEs)."""
        from ..viz import to_mermaid as _to_mermaid
        return _to_mermaid(self)

    # ------------------------------------------------------------------
    # Jupyter rich output
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        n = len(self.records)
        if n == 0:
            return "<UnifiedTracker: 0 operations>"
        libs = sorted({r.library for r in self.records if r.library})
        return f"<UnifiedTracker: {n} operations across {', '.join(libs) or '?'}>"

    def _repr_html_(self) -> str:
        """IPython rich-display hook. Renders a compact summary table,
        followed by the interactive lineage graph, when this tracker is
        the last expression in a Jupyter cell."""
        if not self.records:
            return ('<div style="font-family:sans-serif;color:#666;">'
                    '<b>UnifiedTracker</b> &middot; no operations recorded yet.'
                    '</div>')

        from ..viz import _build_html
        # Compact summary header
        summary = self.get_summary()
        rows = []
        rows.append('<div style="font-family:-apple-system,BlinkMacSystemFont,'
                    '\'Segoe UI\',Roboto,sans-serif;'
                    'border:1px solid #e0e0e0;border-radius:8px;'
                    'padding:14px 18px;margin:8px 0;background:#fafafa;">')
        rows.append('<div style="display:flex;align-items:center;gap:18px;'
                    'margin-bottom:10px;">')
        rows.append('<b style="font-size:15px;color:#1a1a1a;">AutoLineage trace</b>')
        rows.append(f'<span style="color:#666;font-size:13px;">'
                    f'{summary["total_records"]} operations</span>')
        if summary.get("libraries_tracked"):
            rows.append(f'<span style="color:#666;font-size:13px;">'
                        f'{" / ".join(summary["libraries_tracked"])}</span>')
        if summary.get("total_rows_filtered"):
            rows.append(f'<span style="color:#666;font-size:13px;">'
                        f'<b>{summary["total_rows_filtered"]:,}</b> rows filtered</span>')
        rows.append('</div>')

        # Operations table (top 12)
        rows.append('<table style="border-collapse:collapse;font-size:12px;'
                    'margin-top:6px;width:100%;">')
        rows.append('<thead><tr style="background:#f0f0f0;">'
                    '<th style="padding:6px 10px;text-align:left;'
                    'border-bottom:1px solid #ccc;">#</th>'
                    '<th style="padding:6px 10px;text-align:left;'
                    'border-bottom:1px solid #ccc;">category</th>'
                    '<th style="padding:6px 10px;text-align:left;'
                    'border-bottom:1px solid #ccc;">operation</th>'
                    '<th style="padding:6px 10px;text-align:left;'
                    'border-bottom:1px solid #ccc;">shape</th>'
                    '<th style="padding:6px 10px;text-align:right;'
                    'border-bottom:1px solid #ccc;">rows &Delta;</th>'
                    '<th style="padding:6px 10px;text-align:right;'
                    'border-bottom:1px solid #ccc;">ms</th>'
                    '</tr></thead><tbody>')

        max_rows = 12
        for i, rec in enumerate(self.records[:max_rows]):
            shape = ""
            if rec.output_shape:
                shape = str(tuple(rec.output_shape))
            delta = ""
            if (rec.rows_before is not None and rec.rows_after is not None
                    and rec.rows_before != rec.rows_after):
                d = rec.rows_after - rec.rows_before
                delta = f"{d:+,d}"
            dur = f"{rec.duration_ms:.0f}" if rec.duration_ms else ""
            rows.append(
                f'<tr><td style="padding:4px 10px;color:#888;">{i+1}</td>'
                f'<td style="padding:4px 10px;color:#444;">{rec.category}</td>'
                f'<td style="padding:4px 10px;font-family:monospace;">{rec.operation}</td>'
                f'<td style="padding:4px 10px;font-family:monospace;color:#444;">{shape}</td>'
                f'<td style="padding:4px 10px;text-align:right;font-family:monospace;color:#666;">{delta}</td>'
                f'<td style="padding:4px 10px;text-align:right;font-family:monospace;color:#666;">{dur}</td>'
                f'</tr>')

        if len(self.records) > max_rows:
            rows.append(f'<tr><td colspan="6" style="padding:6px 10px;'
                        f'color:#888;font-style:italic;text-align:center;">'
                        f'... and {len(self.records) - max_rows} more operations</td></tr>')

        rows.append('</tbody></table>')
        rows.append('<div style="margin-top:10px;font-size:12px;color:#666;">'
                    'Call <code>.visualize()</code> for the interactive graph, '
                    '<code>.to_dot()</code> for Graphviz, '
                    'or <code>.to_mermaid()</code> for Markdown.'
                    '</div>')
        rows.append('</div>')
        return '\n'.join(rows)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _hash(obj) -> str:
        try:
            h = hashlib.sha256()
            if hasattr(obj, 'shape'):
                h.update(f"{obj.shape}".encode())
            if hasattr(obj, 'columns'):
                h.update(",".join(str(c) for c in obj.columns).encode())
            if hasattr(obj, 'iloc') and len(obj) > 0:
                h.update(str(obj.iloc[0].values.tobytes()).encode())
                if len(obj) > 1:
                    h.update(str(obj.iloc[-1].values.tobytes()).encode())
            elif hasattr(obj, '__len__') and hasattr(obj, '__getitem__'):
                try:
                    h.update(str(obj[:1]).encode())
                except Exception:
                    pass
            return h.hexdigest()[:16]
        except Exception:
            return str(uuid.uuid4())[:16]
