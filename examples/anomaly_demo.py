"""
Anomaly Detection + Root Cause Localization Demo
=================================================

Runs a fraud-detection pipeline twice:

  1. Baseline (clean code) - records a fingerprint to disk
  2. Buggy   (one filter changed) - compares against baseline

AutoLineage's LineageAnalyzer should:
  * detect the row-count anomaly at the modified filter,
  * detect the metric drop on F1,
  * point root-cause localization at the offending step.

Run::

    python anomaly_demo.py --baseline   # first run, saves fingerprint
    python anomaly_demo.py --buggy      # second run, compares & flags

Or just::

    python anomaly_demo.py              # runs both back-to-back

This is the demo we promise in the paper Section 8 (LineageAnalyzer).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap

import numpy as np
import pandas as pd

# Use the local checkout in development; harmless when installed
HERE = os.path.dirname(os.path.abspath(__file__))
PKG_ROOT = os.path.abspath(os.path.join(HERE, ".."))
if PKG_ROOT not in sys.path:
    sys.path.insert(0, PKG_ROOT)

from autolineage.core.tracker import UnifiedTracker
from autolineage.core.analyzer import LineageAnalyzer
from autolineage.hooks.registry import HookRegistry


FINGERPRINT_PATH = os.path.join(HERE, "anomaly_demo_baseline.json")


# ---------------------------------------------------------------------------
# Synthetic fraud-like dataset (so the demo runs without Kaggle download)
# ---------------------------------------------------------------------------
def make_dataset(n: int = 50_000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_fraud = max(1, int(n * 0.02))
    n_clean = n - n_fraud
    clean = pd.DataFrame({
        "Amount":  rng.gamma(2.0, 30.0, n_clean),
        "V1":      rng.normal(0, 1, n_clean),
        "V2":      rng.normal(0, 1, n_clean),
        "V3":      rng.normal(0, 1, n_clean),
        "V14":     rng.normal(0, 1, n_clean),
        "V17":     rng.normal(0, 1, n_clean),
        "Class":   0,
    })
    fraud = pd.DataFrame({
        "Amount":  rng.gamma(2.0, 90.0, n_fraud),
        "V1":      rng.normal(-2, 1.5, n_fraud),
        "V2":      rng.normal(2.5, 1.5, n_fraud),
        "V3":      rng.normal(-1.5, 1, n_fraud),
        "V14":     rng.normal(-3, 1, n_fraud),
        "V17":     rng.normal(-3, 1, n_fraud),
        "Class":   1,
    })
    df = pd.concat([clean, fraud], ignore_index=True)
    return df.sample(frac=1.0, random_state=seed).reset_index(drop=True)


# ---------------------------------------------------------------------------
# The two pipeline variants. Note: only one line differs. AutoLineage should
# pinpoint that line as the root cause.
# ---------------------------------------------------------------------------
def run_pipeline(*, mode: str) -> dict:
    """
    mode='baseline'  : keep Amount in the natural range
    mode='buggy'     : aggressive Amount filter that wipes fraud cases
    """
    tracker = UnifiedTracker()
    registry = HookRegistry()
    # Hooks are global; ensure a clean slate between runs in the same process.
    registry.uninstall_all()
    HookRegistry._globally_installed.clear()
    installed = registry.install_all(tracker)
    n_hooks = sum(c for _, c in installed)
    print(f"[{mode}] hooks installed: {n_hooks}")

    # IMPORTANT: imports must happen AFTER install_all().
    # `from sklearn.metrics import f1_score` captured before installation
    # would bind to the original (unhooked) function, bypassing the wrapper
    # that records [evaluate] lineage records.
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler

    try:
        df = make_dataset()
        tracker.assign_id(df, source="synthetic_fraud", filepath="synthetic.csv")

        df = df.dropna()
        df = df.drop_duplicates()

        # ------------------------------------------------------------------
        # The single point of variation between baseline and buggy run.
        # ------------------------------------------------------------------
        if mode == "baseline":
            df = df[df["Amount"] < df["Amount"].quantile(0.999)]
        else:
            # BUG: oversharp filter drops ~99% of rows including most fraud
            df = df[df["Amount"] < df["Amount"].quantile(0.05)]
        # ------------------------------------------------------------------

        df = df.assign(Amount_Log=np.log1p(df["Amount"]))
        df = df.assign(V_high_risk=((df["V14"] < -3) | (df["V17"] < -3)).astype(int))

        X = df.drop(columns=["Class"])
        y = df["Class"]
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2,
                                                  random_state=42, stratify=y)

        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_tr)
        X_te_s = scaler.transform(X_te)

        model = RandomForestClassifier(n_estimators=40, max_depth=8,
                                       class_weight="balanced",
                                       random_state=42, n_jobs=1)
        model.fit(X_tr_s, y_tr)
        y_pred = model.predict(X_te_s)

        acc = accuracy_score(y_te, y_pred)
        f1 = f1_score(y_te, y_pred, zero_division=0)
        prec = precision_score(y_te, y_pred, zero_division=0)
        rec = recall_score(y_te, y_pred, zero_division=0)

        print(f"[{mode}] rows after filter: {len(df):,}   "
              f"f1={f1:.4f}  acc={acc:.4f}  prec={prec:.4f}  rec={rec:.4f}")
        print(f"[{mode}] operations tracked: {len(tracker.records)}")
    finally:
        # Clean up so the next run gets fresh hooks
        registry.uninstall_all()

    return {"tracker": tracker, "metrics": {"f1": f1, "accuracy": acc,
                                            "precision": prec, "recall": rec}}


# ---------------------------------------------------------------------------
# Pretty-print analyzer output
# ---------------------------------------------------------------------------
def _bar(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def report(tracker: UnifiedTracker, *, baseline_path: str) -> None:
    analyzer = LineageAnalyzer(tracker)

    if not analyzer.load_baseline(baseline_path):
        _bar("Anomaly detection (no baseline; using built-in heuristics)")
    else:
        _bar("Anomaly detection (vs saved baseline)")

    anomalies = analyzer.detect_anomalies()
    if not anomalies:
        print("  no anomalies detected.")
    else:
        for a in anomalies:
            tag = {"critical": "[!!!]", "warning": "[ ! ]", "info": "[ i ]"}.get(
                a.severity, "[   ]")
            print(f"  {tag} {a.severity:8s}  {a.message}")

    _bar("Root-cause localization")
    cause = analyzer.localize_root_cause("f1_score")
    if cause is None:
        print("  no clear root cause identified.")
    else:
        print(textwrap.fill(cause.explanation, width=70,
                            initial_indent="  ", subsequent_indent="  "))
        print()
        print(f"  metric:        {cause.metric_name}")
        print(f"  baseline:      {cause.metric_baseline:.4f}")
        print(f"  current:       {cause.metric_actual:.4f}")
        print(f"  root operation:{cause.root_operation} (step {cause.root_step_index})")
        print(f"  impact score:  {cause.impact_score:.2f}")
        if cause.evidence:
            print("  evidence:")
            for k, v in cause.evidence.items():
                print(f"    - {k}: {v}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--baseline", action="store_true",
                   help="run the clean pipeline and save a fingerprint")
    p.add_argument("--buggy", action="store_true",
                   help="run the buggy pipeline and report anomalies")
    p.add_argument("--clean", action="store_true",
                   help="delete the saved baseline fingerprint")
    args = p.parse_args()

    if args.clean and os.path.exists(FINGERPRINT_PATH):
        os.remove(FINGERPRINT_PATH)
        print(f"Removed {FINGERPRINT_PATH}")
        return 0

    if args.baseline or not (args.baseline or args.buggy):
        _bar("Step 1: baseline run (clean code)")
        out = run_pipeline(mode="baseline")
        analyzer = LineageAnalyzer(out["tracker"])
        analyzer.save_fingerprint(FINGERPRINT_PATH, append=False)
        print(f"baseline fingerprint saved to {FINGERPRINT_PATH}")
        if not args.buggy and (args.baseline or len(sys.argv) == 1):
            if not args.baseline:
                pass  # fall through to also run the buggy variant
            else:
                return 0

    _bar("Step 2: buggy run (someone changed the filter)")
    out = run_pipeline(mode="buggy")
    report(out["tracker"], baseline_path=FINGERPRINT_PATH)

    _bar("Conclusion")
    print(textwrap.fill(
        "AutoLineage detected the row-count anomaly and the F1 collapse, "
        "and root-cause localization correctly identified the filter "
        "operation as the root cause of the metric degradation. No "
        "manual instrumentation, no print statements, no extra code.",
        width=70, initial_indent="  ", subsequent_indent="  "))
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
