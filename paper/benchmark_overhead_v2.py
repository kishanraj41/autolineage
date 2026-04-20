"""
Overhead Benchmark (v2)

Runs the same ML pipeline 5 times WITH AutoLineage and 5 times WITHOUT.
Reports mean, std, overhead percentage, and per-operation cost.

Usage: python paper/benchmark_overhead_v2.py
"""

import os
import sys
import time
import json
import platform
import numpy as np
import pandas as pd

N_TRIALS = 5


def sys_info():
    return {
        'python': sys.version.split()[0],
        'platform': platform.platform(),
        'processor': platform.processor() or 'unknown',
        'pandas': pd.__version__,
        'numpy': np.__version__,
    }


def run_pipeline():
    """One standardized end-to-end pipeline run."""
    np.random.seed(42)
    n = 50000
    df = pd.DataFrame({
        'id': range(n),
        'category': np.random.choice(['A', 'B', 'C', 'D'], n),
        'value1': np.random.randn(n),
        'value2': np.random.exponential(100, n),
        'value3': np.random.randint(0, 100, n),
        'flag': np.random.choice([True, False], n, p=[0.7, 0.3]),
    })

    # Pandas
    df = df.dropna()
    df = df[df['value1'] > -1]
    df = df.drop_duplicates(subset=['category', 'value3'])
    df = df.assign(ratio=df['value2'] / (df['value3'] + 1))
    df = df.rename(columns={'value1': 'v1', 'value2': 'v2'})
    df = df.sort_values('ratio', ascending=False)
    df.groupby('category')['ratio'].mean()
    merged = df.merge(
        df.groupby('category')['v2'].sum().reset_index().rename(columns={'v2': 'cat_total'}),
        on='category'
    )

    # Sklearn
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

    X = merged[['v1', 'v2', 'value3', 'ratio']].copy()
    y = (merged['v1'] > 0).astype(int)

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42)
    s = StandardScaler()
    X_tr_s = s.fit_transform(X_tr)
    X_te_s = s.transform(X_te)

    m = RandomForestClassifier(n_estimators=20, max_depth=5, random_state=42, n_jobs=1)
    m.fit(X_tr_s, y_tr)
    y_p = m.predict(X_te_s)

    accuracy_score(y_te, y_p)
    f1_score(y_te, y_p)
    precision_score(y_te, y_p)
    recall_score(y_te, y_p)


def benchmark_without():
    times = []
    for i in range(N_TRIALS):
        t0 = time.perf_counter()
        run_pipeline()
        dt = time.perf_counter() - t0
        times.append(dt)
        print(f"  Trial {i+1}: {dt:.3f}s")
    return times


def benchmark_with():
    from autolineage.core.tracker import UnifiedTracker
    from autolineage.hooks.registry import HookRegistry

    HookRegistry._globally_installed.clear()
    tracker = UnifiedTracker()
    registry = HookRegistry()
    installed = registry.install_all(tracker)
    total_hooks = sum(c for _, c in installed)
    print(f"  Hooks installed: {total_hooks}")

    times = []
    ops_counts = []
    for i in range(N_TRIALS):
        tracker.records.clear()
        tracker.nodes.clear()
        t0 = time.perf_counter()
        run_pipeline()
        dt = time.perf_counter() - t0
        times.append(dt)
        ops_counts.append(len(tracker.records))
        print(f"  Trial {i+1}: {dt:.3f}s ({len(tracker.records)} ops tracked)")

    registry.uninstall_all()
    return times, ops_counts


if __name__ == "__main__":
    print("=" * 60)
    print("AutoLineage Overhead Benchmark")
    print("=" * 60)
    info = sys_info()
    for k, v in info.items():
        print(f"  {k}: {v}")
    print()

    print("Warmup...")
    run_pipeline()
    print()

    print(f"Running {N_TRIALS} trials WITHOUT AutoLineage:")
    times_without = benchmark_without()
    print()

    print(f"Running {N_TRIALS} trials WITH AutoLineage:")
    times_with, ops_counts = benchmark_with()
    print()

    mean_wo = np.mean(times_without)
    std_wo = np.std(times_without)
    mean_w = np.mean(times_with)
    std_w = np.std(times_with)
    overhead_s = mean_w - mean_wo
    overhead_pct = (overhead_s / mean_wo) * 100
    mean_ops = np.mean(ops_counts)

    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"  Without AutoLineage:  {mean_wo:.3f}s +/- {std_wo:.3f}s")
    print(f"  With AutoLineage:     {mean_w:.3f}s +/- {std_w:.3f}s")
    print(f"  Overhead:             {overhead_s:.3f}s  ({overhead_pct:.1f}%)")
    print(f"  Operations tracked:   {mean_ops:.0f} per run")
    print(f"  Per-operation cost:   {(overhead_s / mean_ops * 1000):.2f}ms")
    print("=" * 60)

    results = {
        'system_info': info,
        'n_trials': N_TRIALS,
        'times_without': times_without,
        'times_with': times_with,
        'ops_per_run': ops_counts,
        'summary': {
            'mean_without_s': mean_wo,
            'std_without_s': std_wo,
            'mean_with_s': mean_w,
            'std_with_s': std_w,
            'overhead_s': overhead_s,
            'overhead_percent': overhead_pct,
            'mean_ops_per_run': mean_ops,
            'per_op_ms': overhead_s / mean_ops * 1000,
        }
    }

    HERE = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(HERE, "benchmark_results_v2.json")
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to: {out_path}")
