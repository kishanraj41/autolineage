"""
Case Study: Debugging a Planted Data Quality Bug

This is the pipeline BOTH participants will debug.
One participant (P1) uses AutoLineage. The other (P2) uses only print statements.

The pipeline has a PLANTED BUG: an overly aggressive Amount filter removes
99.99% of transactions, making the model useless. The task is to find why.

Expected runtime: <1 minute (bug causes very small training set)
Expected output: F1 = 0.0000 or near-zero

Usage:
    # Environment A (P1 - WITH AutoLineage):
    python paper/case_study_pipeline.py

    # Environment B (P2 - WITHOUT AutoLineage):
    # Comment out the two 'import autolineage' lines at top
    python paper/case_study_pipeline.py
"""

import os
import sys

# =============================================================
# TOGGLE THIS LINE TO SWITCH CONDITIONS
# =============================================================
USE_AUTOLINEAGE = True  # Set to False for the manual debugging condition
# =============================================================

if USE_AUTOLINEAGE:
    from autolineage.core.tracker import UnifiedTracker
    from autolineage.hooks.registry import HookRegistry
    from autolineage.core.analyzer import LineageAnalyzer

    HookRegistry._globally_installed.clear()
    tracker = UnifiedTracker()
    registry = HookRegistry()
    registry.install_all(tracker)

# Standard pipeline imports
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "data", "creditcard.csv")

if not os.path.exists(DATA_PATH):
    print(f"ERROR: {DATA_PATH} not found.")
    sys.exit(1)

# ---- Load ----
print("Loading data...")
df = pd.read_csv(DATA_PATH)
print(f"Loaded: {df.shape}")

# ---- Clean ----
print("Cleaning...")
df = df.dropna()
df = df.drop_duplicates()

# =============================================================
# PLANTED BUG: This filter removes 99.99% of transactions.
# Should be 'df[df["Amount"] > 0.01]' (exclude pennies) but was
# written as 'df[df["Amount"] < 0.01]' (keep only pennies).
# =============================================================
df = df[df['Amount'] < 0.01]

# ---- Feature engineering ----
print("Feature engineering...")
df = df.assign(
    Amount_Log=np.log1p(df['Amount']),
    Hour=((df['Time'] / 3600) % 24).astype(int),
)

# ---- Prepare ----
X = df.drop(columns=['Class', 'Time'])
y = df['Class']

# ---- Split ----
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# ---- Scale ----
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

# ---- Train ----
print("Training RandomForest...")
model = RandomForestClassifier(n_estimators=30, max_depth=8,
                                random_state=42, n_jobs=1)
model.fit(X_train_s, y_train)

# ---- Predict ----
y_pred = model.predict(X_test_s)

# ---- Evaluate ----
acc = accuracy_score(y_test, y_pred)
prec = precision_score(y_test, y_pred, zero_division=0)
rec = recall_score(y_test, y_pred, zero_division=0)
f1 = f1_score(y_test, y_pred, zero_division=0)

print()
print("=" * 60)
print("RESULTS")
print("=" * 60)
print(f"  Accuracy:  {acc:.4f}")
print(f"  Precision: {prec:.4f}")
print(f"  Recall:    {rec:.4f}")
print(f"  F1:        {f1:.4f}")
print("=" * 60)
print()
print("The model's F1 is near zero. Something is wrong.")
print("Your task: find the root cause.")
print()

if USE_AUTOLINEAGE:
    print("=" * 60)
    print("AUTOLINEAGE OUTPUT (available for this participant)")
    print("=" * 60)
    summary = tracker.get_summary()
    print(f"Total operations tracked: {summary['total_records']}")
    print(f"Rows filtered: {summary['total_rows_filtered']:,}")
    print()
    print("Full trace:")
    print("-" * 60)
    for i, rec in enumerate(tracker.records):
        d = ''
        if rec.rows_before and rec.rows_after:
            diff = rec.rows_after - rec.rows_before
            if diff != 0:
                d = f' ({diff:+,d} rows)'
        shape = ''
        if rec.input_shape and rec.output_shape:
            shape = f' {rec.input_shape}->{rec.output_shape}'
        extra = ''
        if rec.metadata.get('metric_value') is not None:
            extra = f' = {rec.metadata["metric_value"]:.4f}'
        print(f'  {i+1:2d}. [{rec.category:10s}] {rec.operation}{shape}{d}{extra}')
    print("-" * 60)
    print()

    # Run the analyzer
    print("Anomaly Detection:")
    analyzer = LineageAnalyzer(tracker)
    anomalies = analyzer.detect_anomalies()
    if anomalies:
        for a in anomalies:
            print(f"  [{a.severity:8s}] {a.message}")
    else:
        print("  No anomalies detected.")
    print()

    print("Root Cause Analysis:")
    cause = analyzer.localize_root_cause()
    if cause:
        print(f"  Root: {cause.root_operation} (step {cause.root_step_index})")
        print(f"  Impact: {cause.impact_score:.2f}")
        print(f"  {cause.explanation}")
    else:
        print("  No root cause identified.")
    print()
    registry.uninstall_all()
else:
    print("=" * 60)
    print("NO AUTOLINEAGE (debug manually)")
    print("=" * 60)
    print("You have only the final F1 score. Use print statements,")
    print("add df.shape checks, etc. to find the bug.")
