"""
Unified transformation record.

Every hook provider produces the same TransformationRecord.
"""

import uuid
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple


@dataclass
class TransformationRecord:
    """Records a single tracked operation across any library."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    library: str = ""
    category: str = ""
    operation: str = ""
    parent_ids: List[str] = field(default_factory=list)
    child_id: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    input_shape: Optional[Tuple[int, ...]] = None
    output_shape: Optional[Tuple[int, ...]] = None
    input_columns: Optional[List[str]] = None
    output_columns: Optional[List[str]] = None
    columns_added: Optional[List[str]] = None
    columns_removed: Optional[List[str]] = None
    rows_before: Optional[int] = None
    rows_after: Optional[int] = None
    duration_ms: Optional[float] = None
    content_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def row_delta(self) -> Optional[int]:
        if self.rows_before is not None and self.rows_after is not None:
            return self.rows_after - self.rows_before
        return None

    @property
    def col_delta(self) -> Optional[int]:
        added = len(self.columns_added) if self.columns_added else 0
        removed = len(self.columns_removed) if self.columns_removed else 0
        if added or removed:
            return added - removed
        return None

    def __repr__(self) -> str:
        shape = ""
        if self.input_shape and self.output_shape:
            shape = f" {self.input_shape}->{self.output_shape}"
        return f"<Record {self.library}.{self.operation}{shape}>"
