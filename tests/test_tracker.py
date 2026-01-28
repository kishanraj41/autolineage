"""Tests for tracker module."""

import os
import tempfile
from autolineage.tracker import hash_file, get_file_info, DatasetTracker


def test_hash_file():
    """Test file hashing."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("Hello, World!")
        temp_path = f.name
    
    # Hash it
    file_hash = hash_file(temp_path)
    
    # Verify it's a valid SHA256 hash
    assert file_hash is not None
    assert len(file_hash) == 64  # SHA256 hex string length
    
    # Hash should be consistent
    hash2 = hash_file(temp_path)
    assert file_hash == hash2
    
    # Clean up
    os.remove(temp_path)
    print("✓ hash_file test passed")


def test_get_file_info():
    """Test getting file metadata."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("a,b,c\n1,2,3\n")
        temp_path = f.name
    
    # Get info
    info = get_file_info(temp_path)
    
    assert info is not None
    assert 'filepath' in info
    assert 'filename' in info
    assert 'size' in info
    assert 'format' in info
    assert 'hash' in info
    assert info['format'] == 'csv'
    assert info['size'] > 0
    
    # Clean up
    os.remove(temp_path)
    print("✓ get_file_info test passed")


def test_dataset_tracker():
    """Test DatasetTracker."""
    db_path = "test_tracker.db"
    
    # Clean up if exists
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("a,b\n1,2\n")
        input_file = f.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("a,b\n1,2\n3,4\n")
        output_file = f.name
    
    # Track files
    tracker = DatasetTracker(db_path)
    tracker.start_run("test_script.py")
    
    # Track input
    input_id = tracker.track_file(input_file, "read")
    assert input_id is not None
    
    # Track output
    output_id = tracker.track_file(output_file, "write")
    assert output_id is not None
    
    # Track transformation
    op_id = tracker.track_transformation(
        source_files=[input_file],
        target_files=[output_file],
        function_name="add_row",
        code_snippet="df.append({'a': 3, 'b': 4})"
    )
    assert op_id is not None
    
    # Get summary
    summary = tracker.get_lineage_summary()
    assert summary['datasets_count'] == 2
    assert summary['operations_count'] == 1
    assert summary['lineage_edges_count'] == 1
    
    tracker.end_run()
    tracker.close()
    
    # Clean up
    os.remove(input_file)
    os.remove(output_file)
    os.remove(db_path)
    
    print("✓ DatasetTracker test passed")


if __name__ == "__main__":
    test_hash_file()
    test_get_file_info()
    test_dataset_tracker()
    print("\n✅ All tracker tests passed!")