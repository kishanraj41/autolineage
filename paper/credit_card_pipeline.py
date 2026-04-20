"""
Pipeline 2: Credit Card Fraud Detection

Real-world financial dataset from Kaggle (284,807 transactions).
Demonstrates AutoLineage end-to-end tracking across:
  - Data loading + cleaning
  - Feature engineering
  - Preprocessing
  - Model training + predictions
  - Evaluation with anomaly detection + root cause analysis

Dataset: https://kaggle.com/datasets/mlg-ulb/creditcardfraud
Usage:   python paper/credit_card_pipeline.py
"""

import os
import sys
import time
import json
import pandas as pd
import numpy as np

# ---- AutoLineage setup ----
from autolineage.core.tracker import UnifiedTracker
from autolineage.hooks.registry import HookRegistry
from autolineage.core.analyzer import LineageAnalyzer

HookRegistry._globally_installed.clear()
tracker = UnifiedTracker()
registry = HookRegistry()
installed = registry.install_all(tracker)

print("=" * 70)
print("AutoLineage: Credit Card Fraud Detection Pipeline")
print("=" * 70)
print(f"Hooks: {sum(c for _, c in installed)} across {len(installed)} libraries")
for name, count in installed:
    if count > 0:
        print(f"  {name}: {count}")
print()

# ---- Paths ----
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "data", "creditcard.csv")
OUTPUT_DIR = os.path.join(HERE, "fraud_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

if not os.path.exists(DATA_PATH):
    print(f"ERROR: {DATA_PATH} not found.")
    print("Download from https://kaggle.com/datasets/mlg-ulb/creditcardfraud")
    sys.exit(1)

t_start = time.time()

# ========== STAGE 1: Load ==========
print("Stage 1: Loading data...")
df = pd.read_csv(DATA_PATH)
print(f"  Loaded: {df.shape[0]:,} rows x {df.shape[1]} cols")
print(f"  Fraud rate: {df['Class'].mean():.4%} ({df['Class'].sum():,} frauds)")
print()

# ========== STAGE 2: Clean ==========
print("Stage 2: Cleaning...")
nulls_before = df.isnull().sum().sum()
print(f"  Null values: {nulls_before}")

before_dedup = len(df)
df = df.drop_duplicates()
print(f"  Duplicates removed: {before_dedup - len(df):,}")

amount_threshold = df['Amount'].quantile(0.999)
df = df[df['Amount'] <= amount_threshold]
print(f"  After outlier removal (Amount > {amount_threshold:.2f}): {len(df):,} rows")
print()

# ========== STAGE 3: Feature Engineering ==========
print("Stage 3: Feature engineering...")
df = df.assign(
    Hour=((df['Time'] / 3600) % 24).astype(int),
    Amount_Log=np.log1p(df['Amount']),
    V1_V3_ratio=df['V1'] / (df['V3'] + 1e-8),
    V4_V11_product=df['V4'] * df['V11'],
    V_high_risk=((df['V14'] < -5) | (df['V17'] < -5)).astype(int),
)
print(f"  Added: Hour, Amount_Log, V1_V3_ratio, V4_V11_product, V_high_risk")
print(f"  Shape: {df.shape}")
print()

# ========== STAGE 4: Prepare ==========
print("Stage 4: Preparing features...")
feature_cols = [c for c in df.columns if c not in ['Class', 'Time']]
X = df[feature_cols]
y = df['Class']
print(f"  Feature matrix: {X.shape}")
print(f"  Target: {y.value_counts().to_dict()}")
print()

# ========== STAGE 5: Split ==========
print("Stage 5: Train/test split...")
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"  Train: {X_train.shape[0]:,}  ({y_train.mean():.4%} fraud)")
print(f"  Test:  {X_test.shape[0]:,}  ({y_test.mean():.4%} fraud)")
print()

# ========== STAGE 6: Scale ==========
print("Stage 6: Scaling...")
from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)
print(f"  Scaled: {X_train_s.shape}")
print()

# ========== STAGE 7: Train ==========
print("Stage 7: Training models...")
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

print("  Training RandomForest (n_estimators=100, max_depth=12)...")
rf = RandomForestClassifier(
    n_estimators=100, max_depth=12, min_samples_split=10,
    class_weight='balanced', random_state=42, n_jobs=1)
rf.fit(X_train_s, y_train)

print("  Training LogisticRegression...")
lr = LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42)
lr.fit(X_train_s, y_train)
print()

# ========== STAGE 8: Predict ==========
print("Stage 8: Predictions...")
y_pred_rf = rf.predict(X_test_s)
y_pred_lr = lr.predict(X_test_s)
y_proba_rf = rf.predict_proba(X_test_s)
print(f"  RF predictions: {len(y_pred_rf):,}")
print(f"  LR predictions: {len(y_pred_lr):,}")
print()

# ========== STAGE 9: Evaluate ==========
print("Stage 9: Evaluation...")
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, average_precision_score,
)

rf_acc = accuracy_score(y_test, y_pred_rf)
rf_prec = precision_score(y_test, y_pred_rf)
rf_rec = recall_score(y_test, y_pred_rf)
rf_f1 = f1_score(y_test, y_pred_rf)
rf_auc = roc_auc_score(y_test, y_proba_rf[:, 1])
rf_ap = average_precision_score(y_test, y_proba_rf[:, 1])

lr_acc = accuracy_score(y_test, y_pred_lr)
lr_prec = precision_score(y_test, y_pred_lr)
lr_rec = recall_score(y_test, y_pred_lr)
lr_f1 = f1_score(y_test, y_pred_lr)

print(f"  RandomForest:       Acc={rf_acc:.4f} Prec={rf_prec:.4f} "
      f"Rec={rf_rec:.4f} F1={rf_f1:.4f} AUC={rf_auc:.4f} AP={rf_ap:.4f}")
print(f"  LogisticRegression: Acc={lr_acc:.4f} Prec={lr_prec:.4f} "
      f"Rec={lr_rec:.4f} F1={lr_f1:.4f}")
print()

# ========== STAGE 10: Save ==========
print("Stage 10: Saving outputs...")
results = pd.DataFrame({
    'actual': y_test.values,
    'pred_rf': y_pred_rf,
    'pred_lr': y_pred_lr,
    'proba_rf': y_proba_rf[:, 1],
})
results.to_csv(os.path.join(OUTPUT_DIR, "predictions.csv"), index=False)

metrics = {
    'random_forest': {'accuracy': rf_acc, 'precision': rf_prec, 'recall': rf_rec,
                       'f1': rf_f1, 'auc_roc': rf_auc, 'avg_precision': rf_ap},
    'logistic_regression': {'accuracy': lr_acc, 'precision': lr_prec,
                             'recall': lr_rec, 'f1': lr_f1},
}
with open(os.path.join(OUTPUT_DIR, "metrics.json"), 'w') as f:
    json.dump(metrics, f, indent=2)

elapsed = time.time() - t_start
print(f"\nTotal pipeline time: {elapsed:.1f}s")
print()

# ========== LINEAGE SUMMARY ==========
summary = tracker.get_summary()
print("=" * 70)
print("AUTOLINEAGE: Pipeline Lineage Summary")
print("=" * 70)
print(f"Total operations: {summary['total_records']}")
print(f"Libraries: {summary['libraries_tracked']}")
print(f"Rows filtered: {summary['total_rows_filtered']:,}")
print(f"Column changes: {summary['total_column_changes']}")
print()

for lib, ops in summary['by_library'].items():
    total = sum(ops.values())
    print(f"{lib} ({total} ops):")
    for op, count in sorted(ops.items()):
        print(f"  {op}: {count}")
print()

print("Full trace:")
print("-" * 70)
for i, rec in enumerate(tracker.records):
    delta = ''
    if rec.rows_before is not None and rec.rows_after is not None:
        d = rec.rows_after - rec.rows_before
        if d != 0:
            delta = f' ({d:+,d} rows)'
    shape = ''
    if rec.input_shape:
        shape = f' {rec.input_shape}'
        if rec.output_shape:
            shape += f' -> {rec.output_shape}'
    elif rec.output_shape:
        shape = f' -> {rec.output_shape}'
    extra = ''
    if rec.metadata.get('metric_value') is not None:
        extra = f' = {rec.metadata["metric_value"]:.4f}'
    elif rec.metadata.get('train_size'):
        extra = f' (train={rec.metadata["train_size"]:,}, test={rec.metadata["test_size"]:,})'
    dur = f' [{rec.duration_ms:.0f}ms]' if rec.duration_ms else ''
    h = f' hash:{rec.content_hash[:8]}' if rec.content_hash else ''
    print(f'  {i+1:2d}. [{rec.category:10s}] {rec.operation}{shape}{delta}{extra}{dur}{h}')
print("-" * 70)
print()

# ========== TIMING PROFILE ==========
print("Timing profile (slowest 10 operations):")
print("-" * 70)
for item in tracker.get_timing_profile()[:10]:
    print(f"  {item['operation']:45s} {item['duration_ms']:>8.1f}ms  "
          f"({item['percent_of_total']:>5.1f}%)")
print("-" * 70)
print()

# ========== ANOMALY DETECTION ==========
print("Anomaly Detection (no baseline - self-anomalies):")
print("-" * 70)
analyzer = LineageAnalyzer(tracker)
anomalies = analyzer.detect_anomalies()
if anomalies:
    for a in anomalies:
        print(f"  [{a.severity:8s}] {a.message}")
else:
    print("  No anomalies detected (clean run)")
print()

# Save fingerprint for future comparison
fp_path = os.path.join(OUTPUT_DIR, "fingerprint.json")
analyzer.save_fingerprint(fp_path)
print(f"Fingerprint saved to {fp_path}")
print(f"  ({analyzer.fingerprint().total_records} records)")
print()

# ========== ROOT CAUSE (heuristic, no baseline) ==========
print("Root Cause Analysis (heuristic):")
print("-" * 70)
cause = analyzer.localize_root_cause()
if cause:
    print(f"  Root operation: {cause.root_operation}")
    print(f"  Impact score:   {cause.impact_score:.2f}")
    print(f"  Explanation:    {cause.explanation}")
else:
    print("  No degradation identified - pipeline looks healthy.")
print()

# Save full lineage for paper figures
lineage = {
    'summary': summary,
    'records': [r.to_dict() for r in tracker.records],
    'graph': tracker.get_full_graph(),
    'timing_profile': tracker.get_timing_profile(),
    'metrics': metrics,
    'pipeline_time_seconds': elapsed,
}
with open(os.path.join(OUTPUT_DIR, "lineage.json"), 'w') as f:
    json.dump(lineage, f, indent=2, default=str)

print(f"Outputs saved to: {OUTPUT_DIR}/")
print("Done.")
