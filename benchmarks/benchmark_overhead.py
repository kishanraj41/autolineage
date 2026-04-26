"""
Performance Benchmarks for AutoLineage

Measures the overhead of automatic lineage tracking on common pandas
operations across different dataset sizes. Produces results suitable
for inclusion in academic papers.

Usage:
    python benchmarks/benchmark_overhead.py
    python benchmarks/benchmark_overhead.py --sizes 1000 10000 100000 1000000
    python benchmarks/benchmark_overhead.py --output results.json
"""

import time
import json
import argparse
import statistics
import sys
import os
import tempfile
import gc
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Callable, Tuple
from pathlib import Path

import pandas as pd
import numpy as np


# ============================================================
# BENCHMARK INFRASTRUCTURE
# ============================================================

@dataclass
class BenchmarkResult:
    """Result of a single benchmark."""
    operation: str
    dataset_size: int
    n_columns: int
    baseline_times: List[float] = field(default_factory=list)
    tracked_times: List[float] = field(default_factory=list)

    @property
    def baseline_mean(self) -> float:
        return statistics.mean(self.baseline_times) if self.baseline_times else 0

    @property
    def tracked_mean(self) -> float:
        return statistics.mean(self.tracked_times) if self.tracked_times else 0

    @property
    def overhead_ms(self) -> float:
        return (self.tracked_mean - self.baseline_mean) * 1000

    @property
    def overhead_pct(self) -> float:
        if self.baseline_mean == 0:
            return 0
        return ((self.tracked_mean - self.baseline_mean) / self.baseline_mean) * 100

    @property
    def baseline_std(self) -> float:
        return statistics.stdev(self.baseline_times) if len(self.baseline_times) > 1 else 0

    @property
    def tracked_std(self) -> float:
        return statistics.stdev(self.tracked_times) if len(self.tracked_times) > 1 else 0

    def to_dict(self) -> Dict:
        return {
            'operation': self.operation,
            'dataset_size': self.dataset_size,
            'n_columns': self.n_columns,
            'baseline_mean_s': round(self.baseline_mean, 6),
            'tracked_mean_s': round(self.tracked_mean, 6),
            'baseline_std_s': round(self.baseline_std, 6),
            'tracked_std_s': round(self.tracked_std, 6),
            'overhead_ms': round(self.overhead_ms, 3),
            'overhead_pct': round(self.overhead_pct, 2),
            'n_runs': len(self.baseline_times),
        }


def time_operation(func: Callable, n_runs: int = 10, warmup: int = 2) -> List[float]:
    """
    Time a function over multiple runs with warmup.
    
    Returns list of execution times in seconds.
    """
    # Warmup
    for _ in range(warmup):
        func()
        gc.collect()

    times = []
    for _ in range(n_runs):
        gc.collect()
        start = time.perf_counter()
        func()
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    return times


def generate_dataset(n_rows: int, n_cols: int = 10, null_pct: float = 0.05) -> pd.DataFrame:
    """Generate a realistic test dataset."""
    np.random.seed(42)
    data = {}

    # Mix of column types
    n_numeric = n_cols // 2
    n_string = n_cols // 4
    n_categorical = n_cols - n_numeric - n_string

    for i in range(n_numeric):
        col = np.random.randn(n_rows) * 100
        # Insert nulls
        null_mask = np.random.random(n_rows) < null_pct
        col[null_mask] = np.nan
        data[f'num_{i}'] = col

    categories = ['alpha', 'beta', 'gamma', 'delta', 'epsilon']
    for i in range(n_string):
        data[f'str_{i}'] = np.random.choice(
            [f'val_{j}' for j in range(20)], size=n_rows
        )

    for i in range(n_categorical):
        data[f'cat_{i}'] = np.random.choice(categories, size=n_rows)

    return pd.DataFrame(data)


# ============================================================
# BENCHMARK OPERATIONS
# ============================================================

def bench_read_csv(tmpdir: str, df: pd.DataFrame, n_runs: int) -> Tuple[List[float], List[float]]:
    """Benchmark pd.read_csv."""
    path = os.path.join(tmpdir, 'bench_data.csv')
    df.to_csv(path, index=False)

    def baseline():
        pd.read_csv(path)

    baseline_times = time_operation(baseline, n_runs)
    return baseline_times, path


def bench_to_csv(tmpdir: str, df: pd.DataFrame, n_runs: int) -> List[float]:
    """Benchmark DataFrame.to_csv."""
    path = os.path.join(tmpdir, 'bench_output.csv')

    def op():
        df.to_csv(path, index=False)

    return time_operation(op, n_runs)


def bench_dropna(df: pd.DataFrame, n_runs: int) -> List[float]:
    """Benchmark DataFrame.dropna."""
    def op():
        df.dropna()
    return time_operation(op, n_runs)


def bench_fillna(df: pd.DataFrame, n_runs: int) -> List[float]:
    """Benchmark DataFrame.fillna."""
    def op():
        df.fillna(0)
    return time_operation(op, n_runs)


def bench_merge(df: pd.DataFrame, n_runs: int) -> List[float]:
    """Benchmark DataFrame.merge."""
    # Create a lookup table
    keys = df['cat_0'].unique()
    lookup = pd.DataFrame({
        'cat_0': keys,
        'lookup_val': np.random.randn(len(keys))
    })

    def op():
        df.merge(lookup, on='cat_0', how='left')

    return time_operation(op, n_runs)


def bench_groupby_sum(df: pd.DataFrame, n_runs: int) -> List[float]:
    """Benchmark DataFrame.groupby().sum()."""
    def op():
        df.groupby('cat_0')['num_0'].sum()
    return time_operation(op, n_runs)


def bench_sort_values(df: pd.DataFrame, n_runs: int) -> List[float]:
    """Benchmark DataFrame.sort_values."""
    def op():
        df.sort_values('num_0')
    return time_operation(op, n_runs)


def bench_rename(df: pd.DataFrame, n_runs: int) -> List[float]:
    """Benchmark DataFrame.rename."""
    mapping = {col: f'renamed_{col}' for col in df.columns[:3]}

    def op():
        df.rename(columns=mapping)

    return time_operation(op, n_runs)


def bench_filter(df: pd.DataFrame, n_runs: int) -> List[float]:
    """Benchmark boolean filtering."""
    def op():
        df[df['num_0'] > 0]
    return time_operation(op, n_runs)


def bench_assign(df: pd.DataFrame, n_runs: int) -> List[float]:
    """Benchmark DataFrame.assign."""
    def op():
        df.assign(new_col=lambda x: x['num_0'] * 2)
    return time_operation(op, n_runs)


def bench_drop_duplicates(df: pd.DataFrame, n_runs: int) -> List[float]:
    """Benchmark DataFrame.drop_duplicates."""
    def op():
        df.drop_duplicates(subset=['cat_0'])
    return time_operation(op, n_runs)


def bench_concat(df: pd.DataFrame, n_runs: int) -> List[float]:
    """Benchmark pd.concat."""
    half = len(df) // 2
    df1 = df.iloc[:half]
    df2 = df.iloc[half:]

    def op():
        pd.concat([df1, df2])

    return time_operation(op, n_runs)


def bench_query(df: pd.DataFrame, n_runs: int) -> List[float]:
    """Benchmark DataFrame.query."""
    def op():
        df.query('num_0 > 0 and num_1 < 50')
    return time_operation(op, n_runs)


# ============================================================
# MAIN BENCHMARK RUNNER
# ============================================================

OPERATIONS = {
    'read_csv': None,       # Special handling
    'to_csv': bench_to_csv,  # Special handling
    'dropna': bench_dropna,
    'fillna': bench_fillna,
    'merge': bench_merge,
    'groupby_sum': bench_groupby_sum,
    'sort_values': bench_sort_values,
    'rename': bench_rename,
    'filter': bench_filter,
    'assign': bench_assign,
    'drop_duplicates': bench_drop_duplicates,
    'concat': bench_concat,
    'query': bench_query,
}


def run_benchmarks(
    sizes: List[int] = None,
    n_cols: int = 10,
    n_runs: int = 10,
    verbose: bool = True
) -> List[BenchmarkResult]:
    """
    Run all benchmarks across dataset sizes.
    
    For each operation and size:
    1. Run baseline (no tracking) 
    2. Run with AutoLineage tracking enabled
    3. Compute overhead
    """
    if sizes is None:
        sizes = [1_000, 10_000, 100_000, 500_000]

    results = []
    tmpdir = tempfile.mkdtemp()

    for size in sizes:
        if verbose:
            print(f"\n{'='*60}")
            print(f"  Dataset size: {size:,} rows x {n_cols} columns")
            print(f"{'='*60}")

        df = generate_dataset(size, n_cols)

        for op_name, bench_fn in OPERATIONS.items():
            if verbose:
                print(f"  Benchmarking {op_name}...", end=" ", flush=True)

            result = BenchmarkResult(
                operation=op_name,
                dataset_size=size,
                n_columns=n_cols,
            )

            # --- Phase 1: Baseline (no tracking) ---
            # Make sure no autolineage hooks are active
            _ensure_no_hooks()

            if op_name == 'read_csv':
                path = os.path.join(tmpdir, f'bench_{size}.csv')
                df.to_csv(path, index=False)
                result.baseline_times = time_operation(
                    lambda: pd.read_csv(path), n_runs
                )
            elif op_name == 'to_csv':
                outpath = os.path.join(tmpdir, f'bench_out_{size}.csv')
                result.baseline_times = time_operation(
                    lambda: df.to_csv(outpath, index=False), n_runs
                )
            else:
                result.baseline_times = bench_fn(df, n_runs)

            # --- Phase 2: With AutoLineage tracking ---
            _enable_tracking()

            # Re-generate df with tracking active so it gets registered
            df_tracked = generate_dataset(size, n_cols)
            from autolineage.df_tracker import get_df_tracker
            get_df_tracker().register_df(df_tracked, source="benchmark")

            if op_name == 'read_csv':
                result.tracked_times = time_operation(
                    lambda: pd.read_csv(path), n_runs
                )
            elif op_name == 'to_csv':
                outpath2 = os.path.join(tmpdir, f'bench_out_tracked_{size}.csv')
                result.tracked_times = time_operation(
                    lambda: df_tracked.to_csv(outpath2, index=False), n_runs
                )
            else:
                # Re-wrap bench function with tracked df
                if op_name == 'merge':
                    keys = df_tracked['cat_0'].unique()
                    lookup = pd.DataFrame({'cat_0': keys, 'lookup_val': np.random.randn(len(keys))})
                    result.tracked_times = time_operation(
                        lambda: df_tracked.merge(lookup, on='cat_0', how='left'), n_runs
                    )
                elif op_name == 'concat':
                    half = len(df_tracked) // 2
                    d1, d2 = df_tracked.iloc[:half], df_tracked.iloc[half:]
                    result.tracked_times = time_operation(
                        lambda: pd.concat([d1, d2]), n_runs
                    )
                elif op_name == 'groupby_sum':
                    result.tracked_times = time_operation(
                        lambda: df_tracked.groupby('cat_0')['num_0'].sum(), n_runs
                    )
                elif op_name == 'sort_values':
                    result.tracked_times = time_operation(
                        lambda: df_tracked.sort_values('num_0'), n_runs
                    )
                elif op_name == 'rename':
                    mapping = {col: f'renamed_{col}' for col in df_tracked.columns[:3]}
                    result.tracked_times = time_operation(
                        lambda: df_tracked.rename(columns=mapping), n_runs
                    )
                elif op_name == 'filter':
                    result.tracked_times = time_operation(
                        lambda: df_tracked[df_tracked['num_0'] > 0], n_runs
                    )
                elif op_name == 'assign':
                    result.tracked_times = time_operation(
                        lambda: df_tracked.assign(new_col=lambda x: x['num_0'] * 2), n_runs
                    )
                elif op_name == 'query':
                    result.tracked_times = time_operation(
                        lambda: df_tracked.query('num_0 > 0 and num_1 < 50'), n_runs
                    )
                else:
                    # Generic: dropna, fillna, drop_duplicates
                    result.tracked_times = bench_fn(df_tracked, n_runs)

            _disable_tracking()

            results.append(result)

            if verbose:
                sign = "+" if result.overhead_pct >= 0 else ""
                print(
                    f"baseline={result.baseline_mean*1000:.2f}ms  "
                    f"tracked={result.tracked_mean*1000:.2f}ms  "
                    f"overhead={sign}{result.overhead_pct:.1f}% "
                    f"({sign}{result.overhead_ms:.3f}ms)"
                )

    return results


def _ensure_no_hooks():
    """Make sure no autolineage hooks are active."""
    try:
        from autolineage.hooks import disable_hooks
        from autolineage.transform_hooks import uninstall_transform_hooks
        import io
        from contextlib import redirect_stdout
        # Suppress output
        with redirect_stdout(io.StringIO()):
            try:
                disable_hooks()
            except Exception:
                pass
            try:
                uninstall_transform_hooks()
            except Exception:
                pass
    except ImportError:
        pass


def _enable_tracking():
    """Enable autolineage tracking."""
    import io
    from contextlib import redirect_stdout
    from autolineage.df_tracker import reset_df_tracker
    reset_df_tracker()
    with redirect_stdout(io.StringIO()):
        from autolineage.hooks import enable_hooks
        enable_hooks()


def _disable_tracking():
    """Disable autolineage tracking."""
    import io
    from contextlib import redirect_stdout
    with redirect_stdout(io.StringIO()):
        _ensure_no_hooks()
    from autolineage.df_tracker import reset_df_tracker
    reset_df_tracker()


# ============================================================
# OUTPUT FORMATTING
# ============================================================

def print_summary_table(results: List[BenchmarkResult]):
    """Print a formatted summary table."""
    print(f"\n{'='*90}")
    print(f"  AUTOLINEAGE PERFORMANCE BENCHMARK RESULTS")
    print(f"{'='*90}")
    print(f"  {'Operation':<20} {'Size':>10} {'Baseline':>12} {'Tracked':>12} {'Overhead':>12} {'%':>8}")
    print(f"  {'-'*20} {'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*8}")

    for r in results:
        sign = "+" if r.overhead_ms >= 0 else ""
        print(
            f"  {r.operation:<20} {r.dataset_size:>10,} "
            f"{r.baseline_mean*1000:>10.2f}ms "
            f"{r.tracked_mean*1000:>10.2f}ms "
            f"{sign}{r.overhead_ms:>10.3f}ms "
            f"{sign}{r.overhead_pct:>6.1f}%"
        )

    # Aggregate stats
    all_overheads = [r.overhead_ms for r in results]
    all_pcts = [r.overhead_pct for r in results]
    print(f"\n  {'AGGREGATE':=<70}")
    print(f"  Mean overhead:   {statistics.mean(all_overheads):>10.3f}ms ({statistics.mean(all_pcts):>6.1f}%)")
    print(f"  Median overhead: {statistics.median(all_overheads):>10.3f}ms ({statistics.median(all_pcts):>6.1f}%)")
    print(f"  Max overhead:    {max(all_overheads):>10.3f}ms ({max(all_pcts):>6.1f}%)")
    print(f"  Min overhead:    {min(all_overheads):>10.3f}ms ({min(all_pcts):>6.1f}%)")

    # Per-size summary
    sizes = sorted(set(r.dataset_size for r in results))
    print(f"\n  {'PER-SIZE SUMMARY':=<70}")
    for size in sizes:
        size_results = [r for r in results if r.dataset_size == size]
        avg_pct = statistics.mean([r.overhead_pct for r in size_results])
        avg_ms = statistics.mean([r.overhead_ms for r in size_results])
        print(f"  {size:>10,} rows: avg overhead = {avg_ms:>8.3f}ms ({avg_pct:>6.1f}%)")


def save_results(results: List[BenchmarkResult], output_path: str):
    """Save results to JSON."""
    import platform
    data = {
        'metadata': {
            'python_version': platform.python_version(),
            'pandas_version': pd.__version__,
            'numpy_version': np.__version__,
            'platform': platform.platform(),
            'processor': platform.processor(),
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        },
        'results': [r.to_dict() for r in results],
    }
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\n  Results saved to: {output_path}")


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='AutoLineage Performance Benchmarks')
    parser.add_argument('--sizes', nargs='+', type=int, default=[1000, 10000, 100000, 500000],
                        help='Dataset sizes to benchmark')
    parser.add_argument('--cols', type=int, default=10, help='Number of columns')
    parser.add_argument('--runs', type=int, default=10, help='Number of runs per benchmark')
    parser.add_argument('--output', type=str, default=None, help='Output JSON file path')
    parser.add_argument('--quick', action='store_true', help='Quick run with fewer sizes and runs')
    args = parser.parse_args()

    if args.quick:
        args.sizes = [1000, 10000, 100000]
        args.runs = 5

    print(f"AutoLineage Performance Benchmarks")
    print(f"  Sizes: {args.sizes}")
    print(f"  Columns: {args.cols}")
    print(f"  Runs per benchmark: {args.runs}")

    results = run_benchmarks(
        sizes=args.sizes,
        n_cols=args.cols,
        n_runs=args.runs,
    )

    print_summary_table(results)

    output_path = args.output or 'benchmarks/results.json'
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    save_results(results, output_path)


if __name__ == '__main__':
    main()
