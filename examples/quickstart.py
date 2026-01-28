"""
QuickStart Example - Get started with AutoLineage in 60 seconds
"""

import pandas as pd
from autolineage import DatasetTracker

print("AutoLineage QuickStart Example")
print("="*60)

# 1. Create a tracker
print("\n1. Creating tracker...")
tracker = DatasetTracker()

# 2. Start tracking
print("2. Starting tracking run...")
tracker.start_run("quickstart.py")

# 3. Do your normal data science work
print("3. Doing data science work...")

# Load data
df = pd.DataFrame({
    'product': ['A', 'B', 'C', 'D'],
    'sales': [100, 150, 120, 200],
    'profit': [20, 30, 25, 40]
})
df.to_csv('sales_data.csv', index=False)
tracker.track_file('sales_data.csv', 'write')

# Clean data
df_clean = df[df['sales'] > 100]
df_clean.to_csv('sales_clean.csv', index=False)

tracker.track_transformation(
    source_files=['sales_data.csv'],
    target_files=['sales_clean.csv'],
    function_name='filter_sales',
    code_snippet="df[df['sales'] > 100]"
)

# Aggregate
df_summary = df_clean.groupby('product')['profit'].sum().reset_index()
df_summary.to_csv('sales_summary.csv', index=False)

tracker.track_transformation(
    source_files=['sales_clean.csv'],
    target_files=['sales_summary.csv'],
    function_name='aggregate_profit',
    code_snippet="df.groupby('product')['profit'].sum()"
)

# 4. End tracking
print("4. Ending tracking...")
tracker.end_run()

# 5. View results
print("\n5. Lineage Summary:")
summary = tracker.get_lineage_summary()
print(f"   Tracked {summary['datasets_count']} datasets")
print(f"   Recorded {summary['operations_count']} operations")
print(f"   Created {summary['lineage_edges_count']} lineage edges")

print("\n6. Data Flow:")
for edge in summary['graph']:
    source_name = edge['source'].split('/')[-1]
    target_name = edge['target'].split('/')[-1]
    print(f"   {source_name} → {target_name} ({edge['operation']})")

tracker.close()

print("\n✅ QuickStart completed!")
print("\nNext steps:")
print("  - Check lineage.db for full details")
print("  - Run 'lineage show' to visualize the graph")
print("  - Generate compliance report with 'lineage report'")