"""
Microbenchmark for AutoLineage hook overhead.

This script measures the per-operation cost of AutoLineage's hook wrapper
in isolation, without the noise of a full ML pipeline. The approach:

1. Create a minimal, instrumentable function (no-op under the hood)
2. Call it N times without AutoLineage hooks -> baseline
3. Call it N times with AutoLineage hooks installed -> instrumented
4. Report the per-call difference

Why this is better than full-pipeline timing:
- Signal-to-noise is ~1000x better (microseconds vs. seconds)
- Pipeline confounds (RandomForest variance, GC, thread scheduling) are eliminated
- The measurement isolates the quantity we actually care about

Runtime: ~1 minute.
"""

import gc
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
N_CALLS = 100_000   # calls per trial
N_TRIALS = 20       # independent trials


def _build_microbench_script(use_autolineage: bool, n_calls: int) -> str:
    """Generate a subprocess script that times N pandas operations."""
    autolineage_import = "import autolineage.auto" if use_autolineage else "# (no autolineage)"
    return f"""
import time, gc
{autolineage_import}
import pandas as pd
import numpy as np

# Build a small DataFrame once
df = pd.DataFrame({{'a': np.arange(100), 'b': np.arange(100) * 2}})

gc.collect()
gc.disable()

# Time N calls to a hooked pandas method
t0 = time.perf_counter()
for _ in range({n_calls}):
    _ = df.dropna()
elapsed = time.perf_counter() - t0

gc.enable()

# Report total elapsed time for N calls
print(elapsed)
"""


def run_trial(use_autolineage: bool, n_calls: int) -> float:
    """Run one microbench trial in a fresh subprocess. Returns total seconds."""
    script = _build_microbench_script(use_autolineage, n_calls)
    script_path = SCRIPT_DIR / "_micro_tmp.py"
    script_path.write_text(script)
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            print(f"  trial failed: {result.stderr[-300:]}")
            return None
        return float(result.stdout.strip().splitlines()[-1])
    finally:
        script_path.unlink(missing_ok=True)


def main():
    print("=" * 70)
    print("AutoLineage Microbenchmark — per-operation hook overhead")
    print("=" * 70)
    print(f"Calls per trial: {N_CALLS:,}")
    print(f"Trials per condition: {N_TRIALS}")
    print()

    baseline_times = []
    print(f"Running {N_TRIALS} baseline trials...")
    for t in range(N_TRIALS):
        elapsed = run_trial(use_autolineage=False, n_calls=N_CALLS)
        if elapsed is not None:
            baseline_times.append(elapsed)
            print(f"  trial {t + 1:2d}/{N_TRIALS}: {elapsed:.4f}s "
                  f"({elapsed * 1e6 / N_CALLS:.2f} µs/call)")

    hooked_times = []
    print(f"\nRunning {N_TRIALS} AutoLineage trials...")
    for t in range(N_TRIALS):
        elapsed = run_trial(use_autolineage=True, n_calls=N_CALLS)
        if elapsed is not None:
            hooked_times.append(elapsed)
            print(f"  trial {t + 1:2d}/{N_TRIALS}: {elapsed:.4f}s "
                  f"({elapsed * 1e6 / N_CALLS:.2f} µs/call)")

    if not baseline_times or not hooked_times:
        print("\n[ERROR] insufficient trials")
        sys.exit(1)

    # Convert to per-call microseconds
    baseline_per_call = np.array(baseline_times) / N_CALLS * 1e6  # in µs
    hooked_per_call = np.array(hooked_times) / N_CALLS * 1e6

    b_mean, b_std = baseline_per_call.mean(), baseline_per_call.std(ddof=1)
    h_mean, h_std = hooked_per_call.mean(), hooked_per_call.std(ddof=1)
    overhead_us = h_mean - b_mean
    # 95% CI on the difference (approximation; Welch-style)
    overhead_se = np.sqrt(b_std**2 / len(baseline_per_call) +
                          h_std**2 / len(hooked_per_call))
    ci_low = overhead_us - 1.96 * overhead_se
    ci_high = overhead_us + 1.96 * overhead_se

    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Baseline:        {b_mean:7.3f} ± {b_std:.3f} µs per call")
    print(f"With AutoLineage:{h_mean:7.3f} ± {h_std:.3f} µs per call")
    print()
    print(f"Per-operation overhead: {overhead_us:.3f} µs")
    print(f"95% CI:                 [{ci_low:.3f}, {ci_high:.3f}] µs")
    print()
    print("For paper text:")
    print(f"  Per-operation hook overhead: {overhead_us:.2f} µs "
          f"(95% CI: [{ci_low:.2f}, {ci_high:.2f}] µs), "
          f"measured across {N_TRIALS} trials of {N_CALLS:,} invocations each.")
    print("=" * 70)

    # Also save raw data
    csv_path = SCRIPT_DIR / "microbench_results.csv"
    with open(csv_path, "w") as f:
        f.write("trial,condition,seconds_total,us_per_call\n")
        for i, (bt, ht) in enumerate(zip(baseline_times, hooked_times)):
            f.write(f"{i+1},baseline,{bt:.6f},{bt*1e6/N_CALLS:.4f}\n")
            f.write(f"{i+1},autolineage,{ht:.6f},{ht*1e6/N_CALLS:.4f}\n")
    print(f"\n[OK] Wrote raw data to {csv_path}")


if __name__ == "__main__":
    main()
