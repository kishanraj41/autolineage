"""
DataFrame-level lineage tracking.

Tracks in-memory transformations by attaching lineage metadata to DataFrames
using pandas' attrs system. Each DataFrame gets a unique lineage node ID,
and transformations create edges between parent and child nodes.

This is the core innovation: zero-code lineage tracking for in-memory
operations, not just file I/O.
"""

import uuid
import hashlib
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict


@dataclass
class TransformationRecord:
    """Records a single in-memory transformation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    operation: str = ""              # e.g., "dropna", "merge", "groupby.sum"
    parent_ids: List[str] = field(default_factory=list)
    child_id: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    input_shape: Optional[Tuple[int, int]] = None
    output_shape: Optional[Tuple[int, int]] = None
    input_columns: Optional[List[str]] = None
    output_columns: Optional[List[str]] = None
    columns_added: Optional[List[str]] = None
    columns_removed: Optional[List[str]] = None
    rows_before: Optional[int] = None
    rows_after: Optional[int] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return asdict(self)


class DataFrameLineageTracker:
    """
    Tracks lineage of in-memory DataFrame transformations.
    
    Uses pandas DataFrame.attrs to attach a unique lineage_id to each
    DataFrame without modifying its data. When a transformation method
    is called, the tracker records the parent-child relationship and
    the operation that created it.
    """

    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}       # lineage_id -> node info
        self.transformations: List[TransformationRecord] = []
        self._file_to_node: Dict[str, str] = {}          # filepath -> lineage_id

    def register_df(self, df, source: str = "unknown", filepath: str = None) -> str:
        """
        Register a DataFrame and assign it a lineage ID.
        
        Args:
            df: The pandas DataFrame
            source: How it was created (e.g., "read_csv", "merge", "dropna")
            filepath: Associated file path, if any
            
        Returns:
            The lineage_id assigned to this DataFrame
        """
        lineage_id = str(uuid.uuid4())[:12]

        # Store in DataFrame's attrs (pandas built-in metadata, survives most operations)
        if not hasattr(df, 'attrs'):
            df.attrs = {}
        df.attrs['_lineage_id'] = lineage_id

        # Record node
        self.nodes[lineage_id] = {
            'id': lineage_id,
            'source': source,
            'filepath': filepath,
            'shape': tuple(df.shape),
            'columns': list(df.columns) if hasattr(df, 'columns') else [],
            'dtypes': None,  # Populated lazily on demand to avoid overhead
            'memory_bytes': df.memory_usage(index=True).sum() if hasattr(df, 'memory_usage') else 0,
            'content_hash': self._hash_df(df),
            'created_at': datetime.now().isoformat(),
        }

        if filepath:
            self._file_to_node[filepath] = lineage_id

        return lineage_id

    def get_lineage_id(self, df) -> Optional[str]:
        """Get the lineage ID of a DataFrame, if tracked."""
        if hasattr(df, 'attrs') and '_lineage_id' in df.attrs:
            return df.attrs['_lineage_id']
        return None

    def record_transformation(
        self,
        operation: str,
        parent_df,
        result_df,
        params: Dict[str, Any] = None,
        extra_parents: List = None
    ) -> str:
        """
        Record an in-memory transformation.
        
        Args:
            operation: Name of the operation (e.g., "dropna", "merge")
            parent_df: The input DataFrame(s)
            result_df: The output DataFrame
            params: Parameters passed to the operation
            extra_parents: Additional parent DataFrames (e.g., right side of merge)
            
        Returns:
            The lineage_id of the result DataFrame
        """
        import pandas as pd

        # Get or create parent lineage IDs
        parent_ids = []
        if parent_df is not None:
            pid = self.get_lineage_id(parent_df)
            if pid is None:
                pid = self.register_df(parent_df, source="untracked")
            parent_ids.append(pid)

        if extra_parents:
            for ep in extra_parents:
                if isinstance(ep, pd.DataFrame):
                    epid = self.get_lineage_id(ep)
                    if epid is None:
                        epid = self.register_df(ep, source="untracked")
                    parent_ids.append(epid)

        # Register result
        child_id = self.register_df(result_df, source=operation)

        # Compute column changes
        parent_cols = set()
        if parent_df is not None and hasattr(parent_df, 'columns'):
            parent_cols = set(parent_df.columns)
        result_cols = set(result_df.columns) if hasattr(result_df, 'columns') else set()

        cols_added = sorted(result_cols - parent_cols) if parent_cols else None
        cols_removed = sorted(parent_cols - result_cols) if parent_cols else None

        # Sanitize params for JSON serialization
        safe_params = self._sanitize_params(params) if params else {}

        # Record
        record = TransformationRecord(
            operation=operation,
            parent_ids=parent_ids,
            child_id=child_id,
            parameters=safe_params,
            input_shape=tuple(parent_df.shape) if parent_df is not None and hasattr(parent_df, 'shape') else None,
            output_shape=tuple(result_df.shape) if hasattr(result_df, 'shape') else None,
            input_columns=sorted(parent_cols) if parent_cols else None,
            output_columns=sorted(result_cols) if result_cols else None,
            columns_added=cols_added if cols_added else None,
            columns_removed=cols_removed if cols_removed else None,
            rows_before=len(parent_df) if parent_df is not None and hasattr(parent_df, '__len__') else None,
            rows_after=len(result_df) if hasattr(result_df, '__len__') else None,
        )
        self.transformations.append(record)

        return child_id

    def get_lineage_chain(self, lineage_id: str) -> List[TransformationRecord]:
        """Get full transformation chain leading to a given node."""
        chain = []
        visited = set()
        self._walk_back(lineage_id, chain, visited)
        return list(reversed(chain))

    def _walk_back(self, node_id, chain, visited):
        if node_id in visited:
            return
        visited.add(node_id)
        for t in self.transformations:
            if t.child_id == node_id:
                chain.append(t)
                for pid in t.parent_ids:
                    self._walk_back(pid, chain, visited)

    def get_full_graph(self) -> Dict[str, Any]:
        """Export the full lineage graph as a serializable dict."""
        return {
            'nodes': self.nodes,
            'edges': [t.to_dict() for t in self.transformations],
            'file_mappings': self._file_to_node,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of tracked transformations."""
        op_counts = {}
        for t in self.transformations:
            op_counts[t.operation] = op_counts.get(t.operation, 0) + 1

        total_rows_removed = 0
        total_cols_changed = 0
        for t in self.transformations:
            if t.rows_before is not None and t.rows_after is not None:
                diff = t.rows_before - t.rows_after
                if diff > 0:
                    total_rows_removed += diff
            if t.columns_added:
                total_cols_changed += len(t.columns_added)
            if t.columns_removed:
                total_cols_changed += len(t.columns_removed)

        return {
            'total_dataframes': len(self.nodes),
            'total_transformations': len(self.transformations),
            'operation_counts': op_counts,
            'total_rows_filtered': total_rows_removed,
            'total_column_changes': total_cols_changed,
        }

    def _hash_df(self, df) -> str:
        """Compute a fast fingerprint of a DataFrame (not cryptographic, just identity)."""
        try:
            h = hashlib.sha256()
            # Hash shape + column names only — fast O(1) fingerprint
            h.update(f"{df.shape}".encode())
            if hasattr(df, 'columns'):
                h.update(",".join(str(c) for c in df.columns).encode())
            # Hash first and last row values for identity (constant time)
            if len(df) > 0:
                h.update(str(df.iloc[0].values.tobytes()).encode())
                if len(df) > 1:
                    h.update(str(df.iloc[-1].values.tobytes()).encode())
            return h.hexdigest()[:16]
        except Exception:
            return str(uuid.uuid4())[:16]

    def _sanitize_params(self, params: Dict) -> Dict:
        """Make parameters JSON-serializable."""
        safe = {}
        for k, v in params.items():
            try:
                json.dumps(v)
                safe[k] = v
            except (TypeError, ValueError):
                safe[k] = str(type(v).__name__)
        return safe


# Global instance
_df_tracker: Optional[DataFrameLineageTracker] = None


def get_df_tracker() -> DataFrameLineageTracker:
    """Get or create the global DataFrame lineage tracker."""
    global _df_tracker
    if _df_tracker is None:
        _df_tracker = DataFrameLineageTracker()
    return _df_tracker


def reset_df_tracker():
    """Reset the global DataFrame lineage tracker."""
    global _df_tracker
    _df_tracker = DataFrameLineageTracker()
