"""
Final demo - complete workflow showcase.
"""

import os

# Clean slate
for f in ['lineage.db', 'final_*.csv', 'final_graph.*', 'final_compliance.*']:
    import glob
    for file in glob.glob(f):
        try:
            os.remove(file)
        except:
            pass

print("="*60)
print("AUTOLINEAGE v0.1.0 - FINAL DEMO")
print("="*60)
print("\nThis demo showcases the complete AutoLineage workflow:\n")
print("1. Automatic tracking")
print("2. Data processing pipeline")
print("3. Visual lineage graphs")
print("4. Compliance reporting")
print("5. Complete audit trail")
print("\n" + "="*60)

# Enable automatic tracking
print("\n📦 Step 1: Enabling automatic tracking...")
import autolineage.auto
import pandas as pd
import numpy as np

# Simulate a real ML pipeline
print("\n📊 Step 2: Running ML pipeline...")

# Raw data collection
print("  • Collecting raw data...")
raw_data = pd.DataFrame({
    'customer_id': range(1, 101),
    'age': np.random.randint(18, 80, 100),
    'income': np.random.randint(20000, 150000, 100),
    'credit_score': np.random.randint(300, 850, 100),
    'purchased': np.random.choice([0, 1], 100)
})
raw_data.to_csv('final_raw_data.csv', index=False)

# Data cleaning
print("  • Cleaning data...")
df = pd.read_csv('final_raw_data.csv')
df_clean = df.dropna()
df_clean = df_clean[df_clean['age'] >= 18]
df_clean.to_csv('final_clean_data.csv', index=False)

# Feature engineering
print("  • Engineering features...")
df_features = pd.read_csv('final_clean_data.csv')
df_features['income_age_ratio'] = df_features['income'] / df_features['age']
df_features['risk_score'] = (df_features['credit_score'] / 850) * (df_features['income'] / 150000)
df_features.to_csv('final_features.csv', index=False)

# Train/test split
print("  • Splitting train/test...")
df_all = pd.read_csv('final_features.csv')
train_size = int(0.8 * len(df_all))
df_train = df_all[:train_size]
df_test = df_all[train_size:]
df_train.to_csv('final_train.csv', index=False)
df_test.to_csv('final_test.csv', index=False)

# Model statistics
print("  • Computing statistics...")
stats = df_train.describe()
stats.to_csv('final_statistics.csv')

print("  ✅ Pipeline completed!")

# Get summary
print("\n📈 Step 3: Lineage Summary")
from autolineage.auto import get_summary
summary = get_summary()

print(f"\n  Datasets tracked: {summary['datasets_count']}")
print(f"  Operations: {summary['operations_count']}")
print(f"  Lineage edges: {summary['lineage_edges_count']}")

print("\n  Data Flow:")
for edge in summary['graph']:
    from pathlib import Path
    source = Path(edge['source']).name
    target = Path(edge['target']).name
    print(f"    {source} → {target}")

# Generate visualizations
print("\n🎨 Step 4: Generating visualizations...")
from autolineage.database import LineageDatabase
from autolineage.graph import LineageGraph
from autolineage.auto import _auto_tracker

if _auto_tracker:
    graph = LineageGraph(_auto_tracker.db)
    graph.build()
    
    # PNG
    print("  • Creating static graph (PNG)...")
    graph.visualize_matplotlib('final_graph.png', figsize=(16, 10), dpi=150)
    
    # HTML
    print("  • Creating interactive graph (HTML)...")
    graph.visualize_plotly('final_graph.html')
    
    print("  ✅ Visualizations created!")

# Generate compliance report
print("\n📋 Step 5: Generating EU AI Act compliance report...")
from autolineage.reporter import ComplianceReporter

if _auto_tracker:
    reporter = ComplianceReporter(_auto_tracker.db)
    
    # Markdown
    print("  • Creating markdown report...")
    reporter.save_markdown('final_compliance_report.md')
    
    # JSON
    print("  • Creating JSON report...")
    reporter.save_json('final_compliance_report.json')
    
    print("  ✅ Compliance reports generated!")

# Show what was created
print("\n" + "="*60)
print("✅ DEMO COMPLETE!")
print("="*60)
print("\nGenerated files:")
print("\n📁 Data Files:")
print("  - final_raw_data.csv")
print("  - final_clean_data.csv")
print("  - final_features.csv")
print("  - final_train.csv")
print("  - final_test.csv")
print("  - final_statistics.csv")
print("\n📊 Visualizations:")
print("  - final_graph.png (static)")
print("  - final_graph.html (interactive)")
print("\n📋 Compliance:")
print("  - final_compliance_report.md")
print("  - final_compliance_report.json")
print("\n💾 Database:")
print("  - lineage.db")

print("\n" + "="*60)
print("NEXT STEPS")
print("="*60)
print("\n1. Open final_graph.html in your browser")
print("2. Read final_compliance_report.md")
print("3. Explore lineage.db with: lineage summary")
print("\n" + "="*60)
print("\n🎉 Thank you for trying AutoLineage! 🎉")
print("\nIf you find it useful, please:")
print("  ⭐ Star the repository")
print("  🐛 Report bugs/issues")
print("  💡 Suggest features")
print("\n" + "="*60)