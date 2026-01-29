"""
Test automatic operation tracking.
"""

import os
if os.path.exists('lineage.db'):
    os.remove('lineage.db')

# Enable automatic tracking
import autolineage.auto
import pandas as pd

print("\n" + "="*60)
print("AUTOMATIC OPERATION TRACKING TEST")
print("="*60 + "\n")

# Create initial data
print("1. Creating employees dataset...")
employees = pd.DataFrame({
    'id': [1, 2, 3, 4, 5],
    'name': ['Alice', 'Bob', 'Charlie', 'David', 'Eve'],
    'department': ['Sales', 'Engineering', 'Sales', 'Engineering', 'HR'],
    'salary': [50000, 80000, 55000, 85000, 60000]
})
employees.to_csv('employees.csv', index=False)

# Filter by department
print("2. Filtering by department...")
df = pd.read_csv('employees.csv')  # READ
df_sales = df[df['department'] == 'Sales']
df_sales.to_csv('sales_employees.csv', index=False)  # WRITE
# ↑ Lineage should auto-create: employees.csv → sales_employees.csv

# Calculate average salary
print("3. Calculating average salary...")
df_sales_loaded = pd.read_csv('sales_employees.csv')  # READ
avg_salary = df_sales_loaded['salary'].mean()
summary = pd.DataFrame({'avg_sales_salary': [avg_salary]})
summary.to_csv('sales_summary.csv', index=False)  # WRITE
# ↑ Lineage: sales_employees.csv → sales_summary.csv

# Multi-input operation
print("4. Merging engineering and sales data...")
df_eng = df[df['department'] == 'Engineering']
df_eng.to_csv('eng_employees.csv', index=False)

# Read both
df_sales_read = pd.read_csv('sales_employees.csv')  # READ 1
df_eng_read = pd.read_csv('eng_employees.csv')     # READ 2

# Combine
df_combined = pd.concat([df_sales_read, df_eng_read])
df_combined.to_csv('sales_eng_combined.csv', index=False)  # WRITE
# ↑ Lineage: sales_employees.csv + eng_employees.csv → sales_eng_combined.csv

# Show results
print("\n" + "="*60)
print("LINEAGE GRAPH")
print("="*60)

from autolineage.auto import get_summary
result = get_summary()

if result:
    print(f"\nDatasets: {result['datasets_count']}")
    print(f"Operations: {result['operations_count']}")
    print(f"Lineage edges: {result['lineage_edges_count']}")
    
    print("\n📊 Data Flow:")
    for edge in result['graph']:
        source = edge['source'].split('/')[-1]
        target = edge['target'].split('/')[-1]
        op = edge['operation'] if edge['operation'] else 'unknown'
        print(f"  {source} → {target} (via {op})")

print("\n" + "="*60)
print("✅ Test completed!")
print("="*60)