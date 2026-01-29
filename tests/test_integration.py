"""
Integration tests for AutoLineage.
"""

import os
import sys
import tempfile
import shutil
import pandas as pd
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from autolineage import DatasetTracker, LineageGraph, ComplianceReporter


def test_end_to_end_workflow():
    """Test complete workflow from tracking to reporting."""
    
    # Create temp directory
    test_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    
    try:
        os.chdir(test_dir)
        
        print("\n" + "="*60)
        print("INTEGRATION TEST: End-to-End Workflow")
        print("="*60)
        
        # 1. Create tracker
        print("\n1. Creating tracker...")
        tracker = DatasetTracker('test_lineage.db')
        tracker.start_run('integration_test')
        
        # 2. Enable hooks
        print("2. Enabling hooks...")
        from autolineage.hooks import enable_hooks
        enable_hooks(tracker)
        
        # 3. Create and process data
        print("3. Processing data...")
        
        df1 = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
        df1.to_csv('input.csv', index=False)
        
        df2 = pd.read_csv('input.csv')
        df3 = df2[df2['a'] > 1]
        df3.to_csv('output.csv', index=False)
        
        # 4. Get summary
        print("4. Getting summary...")
        summary = tracker.get_lineage_summary()
        
        assert summary['datasets_count'] >= 2, "Should track at least 2 datasets"
        assert summary['lineage_edges_count'] >= 1, "Should have lineage edges"
        
        print(f"   Datasets: {summary['datasets_count']}")
        print(f"   Edges: {summary['lineage_edges_count']}")
        
        # 5. Generate graph
        print("5. Generating graph...")
        graph = LineageGraph(tracker.db)
        graph.build()
        graph.visualize_matplotlib('test_graph.png')
        
        assert os.path.exists('test_graph.png'), "Graph image should be created"
        print("   ✓ Graph created")
        
        # 6. Generate report
        print("6. Generating compliance report...")
        reporter = ComplianceReporter(tracker.db)
        reporter.save_markdown('test_report.md')
        reporter.save_json('test_report.json')
        
        assert os.path.exists('test_report.md'), "Markdown report should exist"
        assert os.path.exists('test_report.json'), "JSON report should exist"
        print("   ✓ Reports created")
        
        # 7. End tracking
        print("7. Ending tracking...")
        tracker.end_run()
        tracker.close()
        
        print("\n" + "="*60)
        print("✅ INTEGRATION TEST PASSED!")
        print("="*60)
        
        return True
        
    finally:
        # Cleanup
        os.chdir(original_dir)
        shutil.rmtree(test_dir)


def test_multiple_inputs_single_output():
    """Test lineage with multiple input files to single output."""
    
    test_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    
    try:
        os.chdir(test_dir)
        
        print("\n" + "="*60)
        print("INTEGRATION TEST: Multiple Inputs → Single Output")
        print("="*60)
        
        tracker = DatasetTracker('multi_test.db')
        tracker.start_run()
        
        from autolineage.hooks import enable_hooks
        enable_hooks(tracker)
        
        # Create two input files
        df1 = pd.DataFrame({'x': [1, 2, 3]})
        df1.to_csv('input1.csv', index=False)
        
        df2 = pd.DataFrame({'y': [4, 5, 6]})
        df2.to_csv('input2.csv', index=False)
        
        # Read both
        d1 = pd.read_csv('input1.csv')
        d2 = pd.read_csv('input2.csv')
        
        # Merge
        merged = pd.concat([d1, d2], axis=1)
        merged.to_csv('merged.csv', index=False)
        
        # Check lineage
        summary = tracker.get_lineage_summary()
        
        print(f"Datasets: {summary['datasets_count']}")
        print(f"Edges: {summary['lineage_edges_count']}")
        
        # Should have edges from both inputs to output
        assert summary['lineage_edges_count'] >= 2, "Should track both input→output edges"
        
        tracker.end_run()
        tracker.close()
        
        print("✅ Multi-input test passed!")
        return True
        
    finally:
        os.chdir(original_dir)
        shutil.rmtree(test_dir)


def test_numpy_tracking():
    """Test NumPy file tracking."""
    
    test_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    
    try:
        os.chdir(test_dir)
        
        print("\n" + "="*60)
        print("INTEGRATION TEST: NumPy Tracking")
        print("="*60)
        
        tracker = DatasetTracker('numpy_test.db')
        tracker.start_run()
        
        from autolineage.hooks import enable_hooks
        enable_hooks(tracker)
        
        import numpy as np
        
        # Save numpy array
        arr = np.array([1, 2, 3, 4, 5])
        np.save('test_array.npy', arr)
        
        # Load it back
        loaded = np.load('test_array.npy')
        
        # Save text
        np.savetxt('test_text.txt', arr)
        
        summary = tracker.get_lineage_summary()
        print(f"NumPy files tracked: {summary['datasets_count']}")
        
        assert summary['datasets_count'] >= 2, "Should track numpy files"
        
        tracker.end_run()
        tracker.close()
        
        print("✅ NumPy tracking test passed!")
        return True
        
    finally:
        os.chdir(original_dir)
        shutil.rmtree(test_dir)


if __name__ == '__main__':
    print("\n" + "="*60)
    print("RUNNING INTEGRATION TEST SUITE")
    print("="*60)
    
    tests = [
        test_end_to_end_workflow,
        test_multiple_inputs_single_output,
        test_numpy_tracking,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n❌ TEST FAILED: {test.__name__}")
            print(f"   Error: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"TEST RESULTS: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("\n🎉 ALL INTEGRATION TESTS PASSED! 🎉")
    else:
        sys.exit(1)