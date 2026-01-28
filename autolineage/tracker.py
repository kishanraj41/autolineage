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
            # Check if hash changed
            existing_id = self.tracked_files[abs_path]
            # For now, just return existing ID
            # TODO: Handle file modifications/versions
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
        
        print(f"✓ Tracked {operation_type}: {filepath} (ID: {dataset_id[:8]}...)")
        
        return dataset_id
    
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
        self.db.close()