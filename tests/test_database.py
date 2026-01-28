"""Tests for database module."""

import os
import pytest
from autolineage.database import LineageDatabase


def test_database_creation():
    """Test that database is created successfully."""
    db_path = "test_lineage.db"
    
    # Clean up if exists
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Create database
    db = LineageDatabase(db_path)
    
    # Check tables exist
    cursor = db.cursor
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    assert "datasets" in tables
    assert "operations" in tables
    assert "lineage" in tables
    assert "runs" in tables
    
    db.close()
    
    # Clean up
    os.remove(db_path)


def test_add_dataset():
    """Test adding a dataset."""
    db_path = "test_lineage.db"
    
    if os.path.exists(db_path):
        os.remove(db_path)
    
    db = LineageDatabase(db_path)
    
    # Add dataset
    dataset_id = db.add_dataset(
        filepath="data.csv",
        file_hash="abc123",
        size=1024,
        file_format="csv"
    )
    
    assert dataset_id is not None
    assert len(dataset_id) == 36  # UUID length
    
    # Verify it was added
    datasets = db.get_all_datasets()
    assert len(datasets) == 1
    assert datasets[0]['filepath'] == "data.csv"
    
    db.close()
    os.remove(db_path)


def test_add_operation():
    """Test adding an operation."""
    db_path = "test_lineage.db"
    
    if os.path.exists(db_path):
        os.remove(db_path)
    
    db = LineageDatabase(db_path)
    
    # Add operation
    op_id = db.add_operation(
        operation_type="read",
        function_name="read_csv",
        parameters={"sep": ","}
    )
    
    assert op_id is not None
    
    # Verify
    operations = db.get_all_operations()
    assert len(operations) == 1
    assert operations[0]['function_name'] == "read_csv"
    
    db.close()
    os.remove(db_path)


def test_lineage_relationship():
    """Test adding lineage relationship."""
    db_path = "test_lineage.db"
    
    if os.path.exists(db_path):
        os.remove(db_path)
    
    db = LineageDatabase(db_path)
    
    # Add source and target datasets
    source_id = db.add_dataset("input.csv", "hash1", 1024, "csv")
    target_id = db.add_dataset("output.csv", "hash2", 2048, "csv")
    
    # Add operation
    op_id = db.add_operation("transform", "dropna")
    
    # Add lineage
    lineage_id = db.add_lineage(source_id, target_id, op_id)
    
    assert lineage_id is not None
    
    # Get lineage graph
    graph = db.get_lineage_graph()
    assert len(graph) == 1
    assert graph[0]['source'] == "input.csv"
    assert graph[0]['target'] == "output.csv"
    assert graph[0]['operation'] == "dropna"
    
    db.close()
    os.remove(db_path)


if __name__ == "__main__":
    # Run tests
    test_database_creation()
    test_add_dataset()
    test_add_operation()
    test_lineage_relationship()
    print("✅ All database tests passed!")