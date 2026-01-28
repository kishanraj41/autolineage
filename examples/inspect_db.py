"""
Inspect the lineage database contents.
"""

import sqlite3
from datetime import datetime

db = sqlite3.connect("lineage.db")
db.row_factory = sqlite3.Row
cursor = db.cursor()

print("="*60)
print("DATABASE INSPECTION")
print("="*60)

# Count records
datasets = cursor.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]
operations = cursor.execute("SELECT COUNT(*) FROM operations").fetchone()[0]
lineage = cursor.execute("SELECT COUNT(*) FROM lineage").fetchone()[0]
runs = cursor.execute("SELECT COUNT(*) FROM runs").fetchone()[0]

print(f"\nTable Counts:")
print(f"  Datasets: {datasets}")
print(f"  Operations: {operations}")
print(f"  Lineage: {lineage}")
print(f"  Runs: {runs}")

print("\n" + "="*60)
print("DATASETS TABLE")
print("="*60)
for row in cursor.execute("SELECT * FROM datasets"):
    print(f"\nID: {row['id']}")
    print(f"File: {row['filepath']}")
    print(f"Hash: {row['hash'][:16]}...")
    print(f"Size: {row['size']} bytes")
    print(f"Format: {row['format']}")
    print(f"Created: {row['created_at']}")

print("\n" + "="*60)
print("OPERATIONS TABLE")
print("="*60)
for row in cursor.execute("SELECT * FROM operations"):
    print(f"\nID: {row['id']}")
    print(f"Type: {row['operation_type']}")
    print(f"Function: {row['function_name']}")
    print(f"Code: {row['code_snippet']}")
    print(f"Parameters: {row['parameters']}")
    print(f"Executed: {row['executed_at']}")

print("\n" + "="*60)
print("LINEAGE TABLE")
print("="*60)
for row in cursor.execute("SELECT * FROM lineage"):
    print(f"\nID: {row['id']}")
    print(f"Source: {row['source_id']}")
    print(f"Target: {row['target_id']}")
    print(f"Operation: {row['operation_id']}")
    print(f"Type: {row['relationship_type']}")
    print(f"Created: {row['created_at']}")

print("\n" + "="*60)
print("RUNS TABLE")
print("="*60)
for row in cursor.execute("SELECT * FROM runs"):
    print(f"\nID: {row['id']}")
    print(f"Script: {row['script_path']}")
    print(f"Start: {row['start_time']}")
    print(f"End: {row['end_time']}")
    print(f"Status: {row['status']}")

db.close()