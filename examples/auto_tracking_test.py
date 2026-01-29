"""
Test automatic tracking - no manual track_file() calls!
"""

# Clean up old files
import os
if os.path.exists('lineage.db'):
    os.remove('lineage.db')

# THIS IS THE MAGIC LINE - enables automatic tracking
import autolineage.auto

# Now just write normal pandas code!
import pandas as pd

print("\n" + "="*60)
print("AUTOMATIC TRACKING TEST")
print("="*60 + "\n")

# Step 1: Create and save data
print("1. Creating dataset...")
df = pd.DataFrame({
    'name': ['Alice', 'Bob', 'Charlie', 'David'],
    'age': [25, 30, 35, 40],
    'salary': [50000, 60000, 70000, 80000]
})

print("2. Saving to CSV...")
df.to_csv('employees.csv', index=False)
# ↑ This is automatically tracked! No manual logging!

# Step 2: Read and filter
print("\n3. Reading CSV...")
df_loaded = pd.read_csv('employees.csv')
# ↑ Also automatically tracked!

print("4. Filtering data...")
df_filtered = df_loaded[df_loaded['age'] > 30]

print("5. Saving filtered data...")
df_filtered.to_csv('employees_filtered.csv', index=False)
# ↑ Tracked automatically!

# Step 3: Aggregate
print("\n6. Reading filtered data...")
df_filtered_loaded = pd.read_csv('employees_filtered.csv')

print("7. Calculating average salary...")
avg_salary = df_filtered_loaded['salary'].mean()

print("8. Saving summary...")
summary = pd.DataFrame({
    'metric': ['average_salary'],
    'value': [avg_salary]
})
summary.to_csv('summary.csv', index=False)

# Get summary
print("\n" + "="*60)
print("LINEAGE SUMMARY")
print("="*60)

from autolineage.auto import get_summary
result = get_summary()

if result:
    print(f"Datasets tracked: {result['datasets_count']}")
    print(f"Operations: {result['operations_count']}")
    
    print("\n📊 Data Flow:")
    for edge in result['graph']:
        source = edge['source'].split('/')[-1]
        target = edge['target'].split('/')[-1]
        print(f"  {source} → {target}")

print("\n" + "="*60)
print("✅ Automatic tracking test completed!")
print("="*60)
print("\nNotice: You never called track_file() manually!")
print("Everything was tracked automatically! 🎉")