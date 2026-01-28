"""
Basic manual test of AutoLineage tracking.
"""

import os
import pandas as pd
from autolineage.tracker import DatasetTracker

# Clean up old database
if os.path.exists("lineage.db"):
    os.remove("lineage.db")

# Create tracker
tracker = DatasetTracker("lineage.db")

# Start a run
tracker.start_run("basic_test.py")

# Create some test data
print("\n1. Creating test dataset...")
df = pd.DataFrame({
    'name': ['Alice', 'Bob', 'Charlie'],
    'age': [25, 30, 35],
    'city': ['NYC', 'LA', 'Chicago']
})
df.to_csv('test_data.csv', index=False)

# Track the input file
print("\n2. Tracking input file...")
input_id = tracker.track_file('test_data.csv', 'write')

# Perform transformation
print("\n3. Performing transformation...")
df_filtered = df[df['age'] > 26]
df_filtered.to_csv('test_data_filtered.csv', index=False)

# Track the transformation
print("\n4. Tracking transformation...")
tracker.track_transformation(
    source_files=['test_data.csv'],
    target_files=['test_data_filtered.csv'],
    function_name='filter_age',
    code_snippet="df[df['age'] > 26]",
    parameters={'threshold': 26}
)

# End run
print("\n5. Ending run...")
tracker.end_run()

# Get summary
print("\n6. Getting lineage summary...")
summary = tracker.get_lineage_summary()

print(f"\n{'='*60}")
print("LINEAGE SUMMARY")
print(f"{'='*60}")
print(f"Datasets tracked: {summary['datasets_count']}")
print(f"Operations tracked: {summary['operations_count']}")
print(f"Lineage edges: {summary['lineage_edges_count']}")

print(f"\n{'='*60}")
print("DATASETS")
print(f"{'='*60}")
for ds in summary['datasets']:
    print(f"• {ds['filepath']}")
    print(f"  Hash: {ds['hash'][:16]}...")
    print(f"  Size: {ds['size']} bytes")
    print(f"  Format: {ds['format']}")
    print()

print(f"{'='*60}")
print("LINEAGE GRAPH")
print(f"{'='*60}")
for edge in summary['graph']:
    print(f"{edge['source']} → {edge['target']}")
    print(f"  Operation: {edge['operation']} ({edge['operation_type']})")
    print()

tracker.close()

print("✅ Test completed successfully!")
print("\nGenerated files:")
print("  - lineage.db (SQLite database)")
print("  - test_data.csv")
print("  - test_data_filtered.csv")