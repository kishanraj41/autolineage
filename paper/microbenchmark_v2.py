"""
Microbenchmark v2 for AutoLineage hook overhead.

Improvements over v1:
1. WARMUP PHASE — runs a 60-second warmup before measurement to ensure
   the CPU is in sustained-load state, not boost-clock state. This
   eliminates the trial-1-vs-trial-10 thermal drift problem.

2. INNER-LOOP MICRO-MEASUREMENT — instead of timing 100,000 calls in a
   subprocess (which mixes call overhead with import time, GC, and
   process startup), each subprocess does its own timing in tight loops
   and reports just the median per-call cost. This isolates the wrapper
   cost from everything else.

3. INTERLEAVED TRIALS — alternate baseline/autolineage in random order
   so any drift across the experiment averages out instead of biasing
   one condition.

Runtime: ~5-10 minutes including warmup.
"""

import gc
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
N_CALLS_PER_LOOP = 10_000   # calls per timed inner loop
N_INNER_LOOPS = 10          # number of inner loops per trial (median over these)
N_TRIALS = 15               # trials per condition (interleaved)
WARMUP_SECONDS = 60


def _build_microbench_script(use_autolineage: bool) -> str:
    """Generate a subprocess script.

    Each subprocess does many short timed loops and reports the MEDIAN
    per-call time. Median is robust to outliers (GC pauses, OS interrupts).
    """
    autolineage_import = "import autolineage.auto" if use_autolineage else "# (no autolineage)"
    return f"""
import time, gc, sys
{autolineage_import}
import pandas as pd
import numpy as np

# Build a small DataFrame once
df = pd.DataFrame({{'a': np.arange(50), 'b': np.arange(50) * 2}})

# Tiny pre-warmup INSIDE this subprocess so JIT / cache effects settle
for _ in range(1000):
    _ = df.dropna()

gc.collect()
gc.disable()

per_call_times = []
for loop in range({N_INNER_LOOPS}):
    t0 = time.perf_counter()
    for _ in range({N_CALLS_PER_LOOP}):
        _ = df.dropna()
    elapsed = time.perf_counter() - t0
    per_call_times.append(elapsed / {N_CALLS_PER_LOOP} * 1e6)  # microseconds

gc.enable()

# Report median per-call cost (robust to outliers)
median_us = sorted(per_call_times)[len(per_call_times) // 2]
print(median_us)
"""


def run_trial(use_autolineage: bool) -> float:
    """Returns median µs per call."""
    script = _build_microbench_script(use_autolineage)
    script_path = SCRIPT_DIR / "_micro_tmp.py"
    script_path.write_text(script)
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            print(f"  trial failed: {result.stderr[-300:]}")
            return None
        return float(result.stdout.strip().splitlines()[-1])
    finally:
        script_path.unlink(missing_ok=True)


def warmup():
    """Run a sustained CPU load for WARMUP_SECONDS to settle into thermal steady state."""
    print(f"WARMUP: running CPU load for {WARMUP_SECONDS}s to stabilize thermal state...")
    print("       (close other apps, plug in power, don't move the laptop)")
    end = time.time() + WARMUP_SECONDS
    iterations = 0
    while time.time() < end:
        # Pure-Python tight loop — heats up the core and forces sustained clock
        x = 0
        for i in range(1_000_000):
            x += i
        iterations += 1
        remaining = max(0, end - time.time())
        print(f"  warmup iter {iterations}, {remaining:.0f}s remaining", end="\r")
    print(f"\nWarmup complete. Beginning measurement.\n")


def main():
    print("=" * 70)
    print("AutoLineage Microbenchmark v2 — thermally stable")
    print("=" * 70)
    print(f"Calls per inner loop: {N_CALLS_PER_LOOP:,}")
    print(f"Inner loops per trial: {N_INNER_LOOPS}")
    print(f"Trials per condition: {N_TRIALS}")
    print()

    warmup()

    # Build interleaved trial schedule
    schedule = []
    for i in range(N_TRIALS):
        schedule.append(("baseline", i))
        schedule.append(("autolineage", i))
    random.seed(42)
    random.shuffle(schedule)

    baseline_results = [None] * N_TRIALS
    hooked_results = [None] * N_TRIALS

    for step, (condition, trial_idx) in enumerate(schedule):
        use_al = (condition == "autolineage")
        result = run_trial(use_al)
        if result is None:
            print(f"  step {step + 1}/{len(schedule)}: {condition} trial {trial_idx + 1} FAILED")
            continue

        if use_al:
            hooked_results[trial_idx] = result
        else:
            baseline_results[trial_idx] = result

        print(f"  step {step + 1:3d}/{len(schedule)}: {condition:11s} "
              f"trial {trial_idx + 1:2d} -> {result:7.3f} µs/call")

    baseline_results = [x for x in baseline_results if x is not None]
    hooked_results = [x for x in hooked_results if x is not None]

    if not baseline_results or not hooked_results:
        print("\n[ERROR] insufficient trials")
        sys.exit(1)

    b = np.array(baseline_results)
    h = np.array(hooked_results)

    b_mean, b_std = b.mean(), b.std(ddof=1)
    h_mean, h_std = h.mean(), h.std(ddof=1)
    overhead_us = h_mean - b_mean
    overhead_se = np.sqrt(b_std**2 / len(b) + h_std**2 / len(h))
    ci_low = overhead_us - 1.96 * overhead_se
    ci_high = overhead_us + 1.96 * overhead_se

    print()
    print("=" * 70)
    print("RESULTS (thermally stabilized, interleaved)")
    print("=" * 70)
    print(f"Baseline:         {b_mean:8.3f} ± {b_std:.3f} µs per call  (n={len(b)})")
    print(f"With AutoLineage: {h_mean:8.3f} ± {h_std:.3f} µs per call  (n={len(h)})")
    print()
    print(f"Per-operation overhead: {overhead_us:.2f} µs")
    print(f"95% CI:                 [{ci_low:.2f}, {ci_high:.2f}] µs")
    print()
    print("Coefficient of variation:")
    print(f"  Baseline CV:    {100*b_std/b_mean:.1f}%  (lower is better; <10% is good)")
    print(f"  AutoLineage CV: {100*h_std/h_mean:.1f}%")
    print()
    print("For paper text:")
    print(f"  Per-operation hook overhead: {overhead_us:.1f} µs "
          f"(95% CI: [{ci_low:.0f}, {ci_high:.0f}] µs), "
          f"measured across {len(b)} interleaved trials per condition.")
    print("=" * 70)

    csv_path = SCRIPT_DIR / "microbench_v2_results.csv"
    with open(csv_path, "w") as f:
        f.write("trial,condition,us_per_call\n")
        for i, v in enumerate(baseline_results):
            f.write(f"{i+1},baseline,{v:.4f}\n")
        for i, v in enumerate(hooked_results):
            f.write(f"{i+1},autolineage,{v:.4f}\n")
    print(f"\n[OK] Wrote raw data to {csv_path}")


if __name__ == "__main__":
    main()
