"""
Test graph visualization.
"""

import os
if os.path.exists('lineage.db'):
    os.remove('lineage.db')

# Enable automatic tracking
import autolineage.auto
import pandas as pd

print("\n" + "="*60)
print("GRAPH VISUALIZATION TEST")
print("="*60 + "\n")

# Create a more complex pipeline
print("1. Creating test data...")
df1 = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
df1.to_csv('raw_data_1.csv', index=False)

df2 = pd.DataFrame({'a': [7, 8, 9], 'b': [10, 11, 12]})
df2.to_csv('raw_data_2.csv', index=False)

print("2. Cleaning data...")
d1 = pd.read_csv('raw_data_1.csv')
d1_clean = d1.dropna()
d1_clean.to_csv('clean_data_1.csv', index=False)

d2 = pd.read_csv('raw_data_2.csv')
d2_clean = d2.dropna()
d2_clean.to_csv('clean_data_2.csv', index=False)

print("3. Merging data...")
clean1 = pd.read_csv('clean_data_1.csv')
clean2 = pd.read_csv('clean_data_2.csv')
merged = pd.concat([clean1, clean2])
merged.to_csv('merged_data.csv', index=False)

print("4. Creating summary...")
final = pd.read_csv('merged_data.csv')
summary = final.describe()
summary.to_csv('final_summary.csv')

# Generate visualizations
print("\n" + "="*60)
print("GENERATING VISUALIZATIONS")
print("="*60 + "\n")

from autolineage.tracker import DatasetTracker
from autolineage.graph import LineageGraph

# Get tracker from auto module
from autolineage.auto import _auto_tracker

if _auto_tracker:
    # Create graph
    graph = LineageGraph(_auto_tracker.db)
    graph.build()
    
    # Show stats
    stats = graph.get_stats()
    print(f"Graph Statistics:")
    print(f"  Nodes: {stats['nodes']}")
    print(f"  Edges: {stats['edges']}")
    print(f"  Is DAG: {stats['is_dag']}")
    print(f"  Sources: {stats['sources']}")
    print(f"  Sinks: {stats['sinks']}")
    
    # Generate matplotlib graph
    print("\n5. Generating static graph (PNG)...")
    graph.visualize_matplotlib('lineage_graph.png')
    
    # Generate plotly graph
    print("6. Generating interactive graph (HTML)...")
    graph.visualize_plotly('lineage_graph.html')
    
    # Text representation
    print("\n7. Text representation:")
    print(graph.to_text())

print("\n" + "="*60)
print("✅ Visualization test completed!")
print("="*60)
print("\nGenerated files:")
print("  - lineage_graph.png (static image)")
print("  - lineage_graph.html (interactive - open in browser!)")
print("\nTry opening lineage_graph.html in your browser! 🌐")