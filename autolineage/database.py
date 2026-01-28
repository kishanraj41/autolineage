"""
Database module for storing lineage metadata.
Uses SQLite for simplicity and portability.
"""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


class LineageDatabase:
    """Manages SQLite database for lineage tracking."""
    
    def __init__(self, db_path: str = "lineage.db"):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row  # Return rows as dicts
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        """Create database schema if it doesn't exist."""
        
        # Datasets table - stores information about data files
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS datasets (
                id TEXT PRIMARY KEY,
                filepath TEXT NOT NULL,
                hash TEXT NOT NULL,
                size INTEGER,
                format TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        
        # Operations table - stores transformations/operations
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS operations (
                id TEXT PRIMARY KEY,
                operation_type TEXT NOT NULL,
                function_name TEXT,
                code_snippet TEXT,
                parameters TEXT,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Lineage table - stores relationships between datasets
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS lineage (
                id TEXT PRIMARY KEY,
                source_id TEXT,
                target_id TEXT,
                operation_id TEXT,
                relationship_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES datasets(id),
                FOREIGN KEY (target_id) REFERENCES datasets(id),
                FOREIGN KEY (operation_id) REFERENCES operations(id)
            )
        """)
        
        # Runs table - stores execution runs
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                script_path TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                status TEXT,
                metadata TEXT
            )
        """)
        
        # Run datasets - many-to-many relationship
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS run_datasets (
                run_id TEXT,
                dataset_id TEXT,
                role TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(id),
                FOREIGN KEY (dataset_id) REFERENCES datasets(id),
                PRIMARY KEY (run_id, dataset_id)
            )
        """)
        
        self.conn.commit()
    
    def add_dataset(
        self, 
        filepath: str, 
        file_hash: str, 
        size: int,
        file_format: str = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Add a dataset to the database.
        
        Args:
            filepath: Path to the dataset file
            file_hash: SHA256 hash of the file
            size: File size in bytes
            file_format: File format (csv, parquet, json, etc.)
            metadata: Additional metadata as dict
            
        Returns:
            Dataset ID (UUID)
        """
        dataset_id = str(uuid.uuid4())
        
        # Convert metadata dict to JSON string
        import json
        metadata_json = json.dumps(metadata) if metadata else None
        
        self.cursor.execute("""
            INSERT INTO datasets (id, filepath, hash, size, format, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (dataset_id, filepath, file_hash, size, file_format, metadata_json))
        
        self.conn.commit()
        return dataset_id
    
    def add_operation(
        self,
        operation_type: str,
        function_name: str = None,
        code_snippet: str = None,
        parameters: Dict[str, Any] = None
    ) -> str:
        """
        Add an operation to the database.
        
        Args:
            operation_type: Type of operation (read, write, transform)
            function_name: Name of function called (e.g., 'read_csv')
            code_snippet: Code that performed the operation
            parameters: Parameters passed to the function
            
        Returns:
            Operation ID (UUID)
        """
        operation_id = str(uuid.uuid4())
        
        import json
        params_json = json.dumps(parameters) if parameters else None
        
        self.cursor.execute("""
            INSERT INTO operations (id, operation_type, function_name, code_snippet, parameters)
            VALUES (?, ?, ?, ?, ?)
        """, (operation_id, operation_type, function_name, code_snippet, params_json))
        
        self.conn.commit()
        return operation_id
    
    def add_lineage(
        self,
        source_id: str,
        target_id: str,
        operation_id: str,
        relationship_type: str = "derived_from"
    ) -> str:
        """
        Add a lineage relationship between datasets.
        
        Args:
            source_id: Source dataset ID
            target_id: Target dataset ID
            operation_id: Operation that created the relationship
            relationship_type: Type of relationship
            
        Returns:
            Lineage ID (UUID)
        """
        lineage_id = str(uuid.uuid4())
        
        self.cursor.execute("""
            INSERT INTO lineage (id, source_id, target_id, operation_id, relationship_type)
            VALUES (?, ?, ?, ?, ?)
        """, (lineage_id, source_id, target_id, operation_id, relationship_type))
        
        self.conn.commit()
        return lineage_id
    
    def start_run(self, script_path: str = None) -> str:
        """
        Start a new tracking run.
        
        Args:
            script_path: Path to script being tracked
            
        Returns:
            Run ID (UUID)
        """
        run_id = str(uuid.uuid4())
        
        self.cursor.execute("""
            INSERT INTO runs (id, script_path, start_time, status)
            VALUES (?, ?, ?, ?)
        """, (run_id, script_path, datetime.now(), "running"))
        
        self.conn.commit()
        return run_id
    
    def end_run(self, run_id: str, status: str = "completed"):
        """
        Mark a run as completed.
        
        Args:
            run_id: Run ID
            status: Final status (completed, failed, etc.)
        """
        self.cursor.execute("""
            UPDATE runs 
            SET end_time = ?, status = ?
            WHERE id = ?
        """, (datetime.now(), status, run_id))
        
        self.conn.commit()
    
    def get_all_datasets(self):
        """Get all datasets from database."""
        self.cursor.execute("SELECT * FROM datasets ORDER BY created_at DESC")
        return self.cursor.fetchall()
    
    def get_all_operations(self):
        """Get all operations from database."""
        self.cursor.execute("SELECT * FROM operations ORDER BY executed_at DESC")
        return self.cursor.fetchall()
    
    def get_lineage_graph(self):
        """
        Get full lineage graph as edges.
        
        Returns:
            List of (source, target, operation) tuples
        """
        self.cursor.execute("""
            SELECT 
                d1.filepath as source,
                d2.filepath as target,
                o.function_name as operation,
                o.operation_type,
                l.created_at
            FROM lineage l
            JOIN datasets d1 ON l.source_id = d1.id
            JOIN datasets d2 ON l.target_id = d2.id
            JOIN operations o ON l.operation_id = o.id
            ORDER BY l.created_at
        """)
        return self.cursor.fetchall()
    
    def close(self):
        """Close database connection."""
        self.conn.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()