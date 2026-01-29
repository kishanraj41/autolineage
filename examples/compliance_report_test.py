"""
Test EU AI Act compliance report generation.
"""

import os
if os.path.exists('lineage.db'):
    os.remove('lineage.db')

# Generate some lineage data
import autolineage.auto
import pandas as pd

print("Generating test data for compliance report...\n")

# Create training data
df_raw = pd.DataFrame({
    'feature_1': [1, 2, 3, 4, 5],
    'feature_2': [10, 20, 30, 40, 50],
    'target': [0, 1, 0, 1, 0]
})
df_raw.to_csv('training_data_raw.csv', index=False)

# Clean data
df = pd.read_csv('training_data_raw.csv')
df_clean = df.dropna()
df_clean.to_csv('training_data_clean.csv', index=False)

# Feature engineering
df_train = pd.read_csv('training_data_clean.csv')
df_train['feature_3'] = df_train['feature_1'] * df_train['feature_2']
df_train.to_csv('training_data_final.csv', index=False)

# Generate compliance report
print("\n" + "="*60)
print("GENERATING COMPLIANCE REPORT")
print("="*60 + "\n")

from autolineage.database import LineageDatabase
from autolineage.reporter import ComplianceReporter
from autolineage.auto import _auto_tracker

if _auto_tracker:
    reporter = ComplianceReporter(_auto_tracker.db)
    
    # Generate markdown
    reporter.save_markdown('compliance_report.md')
    
    # Generate JSON
    reporter.save_json('compliance_report.json')
    
    print("\n" + "="*60)
    print("✅ Reports generated!")
    print("="*60)
    print("\nGenerated files:")
    print("  - compliance_report.md (human-readable)")
    print("  - compliance_report.json (machine-readable)")
    print("\nOpen compliance_report.md to see the full report!")