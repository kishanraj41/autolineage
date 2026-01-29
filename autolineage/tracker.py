"""
Core tracking module for automatic lineage capture.
"""

import hashlib
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from .database import LineageDatabase


def hash_file(filepath: str) -> str:
    """
    Generate SHA256 hash of a file.
    
    Args:
        filepath: Path to file
        
    Returns:
        SHA256 hash as hex string
    """
    sha256 = hashlib.sha256()
    
    try:
        with open(filepath, 'rb') as f:
            # Read in chunks for memory efficiency
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        print(f"Error hashing file {filepath}: {e}")
        return None


def get_file_info(filepath: str) -> Dict[str, Any]:
    """
    Get metadata about a file.
    
    Args:
        filepath: Path to file
        
    Returns:
        Dictionary with file metadata
    """
    path = Path(filepath)
    
    if not path.exists():
        return None
    
    stat = path.stat()
    
    return {
        'filepath': str(path.absolute()),
        'filename': path.name,
        'size': stat.st_size,
        'format': path.suffix[1:] if path.suffix else None,  # Remove leading dot
        'modified': datetime.fromtimestamp(stat.st_mtime),
        'hash': hash_file(filepath)
    }


class DatasetTracker:
    """Tracks datasets and their lineage."""
    
    def __init__(self, db_path: str = "lineage.db"):
        """
        Initialize tracker.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db = LineageDatabase(db_path)
        self.current_run_id = None
        self.tracked_files = {}  # filepath -> dataset_id mapping
        
        # NEW: Track recent file operations for automatic lineage
        self.recent_reads = []   # List of recently read files
        self.recent_writes = []  # List of recently written files
        self.last_operation_code = None
    
    
    def track_file(
        self, 
        filepath: str, 
        operation_type: str = "read",
        metadata: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        Track a file (dataset).
        
        Args:
            filepath: Path to file
            operation_type: Type of operation (read/write)
            metadata: Additional metadata
            
        Returns:
            Dataset ID if successful, None otherwise
        """
        # Get file info
        file_info = get_file_info(filepath)
        
        if not file_info:
            print(f"Warning: Could not track file {filepath} (not found)")
            return None
        
        # Check if already tracked
        abs_path = file_info['filepath']
        file_hash = file_info['hash']
        
        if abs_path in self.tracked_files:
            existing_id = self.tracked_files[abs_path]
            
            # NEW: Still track in recent operations
            if operation_type == "read":
                if abs_path not in self.recent_reads:
                    self.recent_reads.append(abs_path)
            elif operation_type == "write":
                if abs_path not in self.recent_writes:
                    self.recent_writes.append(abs_path)
                    # Auto-create lineage from recent reads to this write
                    self._auto_create_lineage(abs_path)
            
            return existing_id
        
        # Add to database
        dataset_id = self.db.add_dataset(
            filepath=abs_path,
            file_hash=file_hash,
            size=file_info['size'],
            file_format=file_info['format'],
            metadata=metadata
        )
        
        # Cache it
        self.tracked_files[abs_path] = dataset_id
        
        # NEW: Track in recent operations
        if operation_type == "read":
            self.recent_reads.append(abs_path)
        elif operation_type == "write":
            self.recent_writes.append(abs_path)
            # Auto-create lineage from recent reads to this write
            self._auto_create_lineage(abs_path)
        
        print(f"✓ Tracked {operation_type}: {filepath} (ID: {dataset_id[:8]}...)")
        
        return dataset_id
    def _auto_create_lineage(self, output_file):
        """
        Automatically create lineage from recent reads to this write.
        
        Args:
            output_file: File that was just written
        """
        if not self.recent_reads:
            return  # No inputs to link
        
        # Create operation for this transformation
        import inspect
        
        # Try to get calling function info
        frame = inspect.currentframe()
        caller_frame = frame.f_back.f_back.f_back  # Go up the stack
        
        function_name = "unknown"
        code_snippet = None
        
        if caller_frame:
            function_name = caller_frame.f_code.co_name
            # Get a few lines of code context
            try:
                import linecache
                filename = caller_frame.f_code.co_filename
                lineno = caller_frame.f_lineno
                code_snippet = linecache.getline(filename, lineno).strip()
            except:
                pass
        
        # Create operation
        operation_id = self.db.add_operation(
            operation_type='transform',
            function_name=function_name,
            code_snippet=code_snippet
        )
        
        # Link all recent reads to this write
        output_id = self.tracked_files.get(output_file)
        if output_id:
            for input_file in self.recent_reads:
                input_id = self.tracked_files.get(input_file)
                if input_id:
                    self.db.add_lineage(
                        source_id=input_id,
                        target_id=output_id,
                        operation_id=operation_id
                    )
        
        # Clear recent reads after creating lineage
        self.recent_reads = []
        
    def track_transformation(
        self,
        source_files: list,
        target_files: list,
        function_name: str,
        code_snippet: str = None,
        parameters: Dict[str, Any] = None
    ) -> str:
        """
        Track a transformation from source files to target files.
        
        Args:
            source_files: List of input file paths
            target_files: List of output file paths
            function_name: Name of transformation function
            code_snippet: Code that performed transformation
            parameters: Function parameters
            
        Returns:
            Operation ID
        """
        # Track source files
        source_ids = []
        for filepath in source_files:
            dataset_id = self.track_file(filepath, "read")
            if dataset_id:
                source_ids.append(dataset_id)
        
        # Track target files
        target_ids = []
        for filepath in target_files:
            dataset_id = self.track_file(filepath, "write")
            if dataset_id:
                target_ids.append(dataset_id)
        
        # Add operation
        operation_id = self.db.add_operation(
            operation_type="transform",
            function_name=function_name,
            code_snippet=code_snippet,
            parameters=parameters
        )
        
        # Add lineage relationships
        for source_id in source_ids:
            for target_id in target_ids:
                self.db.add_lineage(
                    source_id=source_id,
                    target_id=target_id,
                    operation_id=operation_id,
                    relationship_type="derived_from"
                )
        
        print(f"✓ Tracked transformation: {function_name}")
        
        return operation_id
    
    def operation(self, operation_type, function_name):
        """
        Create an operation context for tracking.
        
        Args:
            operation_type: Type of operation (transform, aggregate, etc.)
            function_name: Name of the function
            
        Returns:
            LineageContext instance
        """
        return LineageContext(self, operation_type, function_name)
    
    def start_run(self, script_path: str = None):
        """Start a new tracking run."""
        self.current_run_id = self.db.start_run(script_path)
        print(f"✓ Started tracking run: {self.current_run_id[:8]}...")
        return self.current_run_id
    
    def end_run(self, status: str = "completed"):
        """End the current tracking run."""
        if self.current_run_id:
            self.db.end_run(self.current_run_id, status)
            print(f"✓ Ended tracking run: {self.current_run_id[:8]}... ({status})")
            self.current_run_id = None
    
    def get_lineage_summary(self):
        """Get summary of tracked lineage."""
        datasets = self.db.get_all_datasets()
        operations = self.db.get_all_operations()
        graph_edges = self.db.get_lineage_graph()
        
        return {
            'datasets_count': len(datasets),
            'operations_count': len(operations),
            'lineage_edges_count': len(graph_edges),
            'datasets': datasets,
            'operations': operations,
            'graph': graph_edges
        }
    
    def close(self):
        """Close tracker and database connection."""
        if hasattr(self, 'db') and self.db:
            self.db.close()
            print("✓ Tracker closed")
    
class LineageContext:
    """
    Context manager for tracking operations.
    
    Usage:
        with tracker.operation('transform', 'filter_age') as op:
            df_filtered = df[df['age'] > 30]
            op.add_input('data.csv')
            op.add_output('filtered.csv')
    """
    
    def __init__(self, tracker, operation_type, function_name):
        self.tracker = tracker
        self.operation_type = operation_type
        self.function_name = function_name
        self.inputs = []
        self.outputs = []
        self.code_snippet = None
        self.parameters = {}
        self.operation_id = None
    
    def add_input(self, filepath):
        """Add input file to this operation."""
        self.inputs.append(filepath)
    
    def add_output(self, filepath):
        """Add output file to this operation."""
        self.outputs.append(filepath)
    
    def set_code(self, code):
        """Set code snippet for this operation."""
        self.code_snippet = code
    
    def set_params(self, **kwargs):
        """Set parameters for this operation."""
        self.parameters.update(kwargs)
    
    def __enter__(self):
        """Enter context."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and save operation."""
        if exc_type is None:  # No exception
            # Create operation
            self.operation_id = self.tracker.db.add_operation(
                operation_type=self.operation_type,
                function_name=self.function_name,
                code_snippet=self.code_snippet,
                parameters=self.parameters
            )
            
            # Create lineage relationships
            for input_file in self.inputs:
                input_id = self.tracker.track_file(input_file, 'read')
                for output_file in self.outputs:
                    output_id = self.tracker.track_file(output_file, 'write')
                    if input_id and output_id:
                        self.tracker.db.add_lineage(
                            source_id=input_id,
                            target_id=output_id,
                            operation_id=self.operation_id
                        )
            
            print(f"✓ Operation tracked: {self.function_name}") 