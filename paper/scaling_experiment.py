"""
Scaling experiment for AutoLineage Paper 1.

Measures AutoLineage overhead as a function of dataset size.
Generates both the raw data table and the matplotlib figure for Figure 2.

Usage:
    Place this script in autolineage/paper/ and run:

        cd paper
        python scaling_experiment.py

Requires:
    - paper/data/creditcard.csv (from Kaggle)
    - autolineage >= 0.3.0 installed (`pip install -e .` from repo root)
    - matplotlib, numpy, pandas, scikit-learn

Output:
    - scaling_results.csv (raw measurements)
    - figures/scaling.pdf (Figure 2 for the paper)
    - figures/scaling.png (for README / web preview)
    - Printed summary table

Runtime: approximately 20-40 minutes on an Intel i7-12700H.
"""

import gc
import os
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# We do NOT import autolineage at module level. The scaling experiment needs
# to import it freshly in each AutoLineage-enabled run, so that hooks install
# cleanly against the current pandas/sklearn. See `run_trial_subprocess` below.
# ---------------------------------------------------------------------------

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt


# Paper-quality figure settings
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 11,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.dpi": 120,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})


SCRIPT_DIR = Path(__file__).resolve().parent
DATA_PATH = SCRIPT_DIR / "data" / "creditcard.csv"
RESULTS_CSV = SCRIPT_DIR / "scaling_results.csv"
FIGURE_PATH_PDF = SCRIPT_DIR / "figures" / "scaling.pdf"
FIGURE_PATH_PNG = SCRIPT_DIR / "figures" / "scaling.png"
FIGURE_PATH_PDF.parent.mkdir(parents=True, exist_ok=True)

# Dataset sizes to test (rows). Five points spanning 3 orders of magnitude.
SIZES = [1_000, 10_000, 100_000, 284_807, 1_000_000]

# Number of repeated trials per (size, condition) cell.
# 5 is enough for reliable means; increase if you have compute to spare.
N_TRIALS = 5


def _build_trial_script(df_path, use_autolineage):
    """Generate a self-contained Python script for one trial."""
    autolineage_import = "import autolineage.auto" if use_autolineage else "# (no autolineage)"
    return f"""
import time, gc, sys
{autolineage_import}
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score,
)

gc.collect()

df = pd.read_pickle(r"{df_path}")
t0 = time.perf_counter()

df = df.drop_duplicates()
df = df[df['Amount'] > 0.01]
df = df.assign(
    log_amount=np.log1p(df['Amount']),
    hour_of_day=(df['Time'] % 86400) / 3600,
)

X = df.drop(columns=['Class'])
y = df['Class']
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y,
)

scaler = StandardScaler()
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)

n_est = min(50, max(10, len(df) // 5000))
model = RandomForestClassifier(n_estimators=n_est, n_jobs=-1, random_state=42)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]
_ = accuracy_score(y_test, y_pred)
_ = precision_score(y_test, y_pred, zero_division=0)
_ = recall_score(y_test, y_pred, zero_division=0)
_ = f1_score(y_test, y_pred, zero_division=0)
_ = roc_auc_score(y_test, y_proba)

elapsed = time.perf_counter() - t0
print(elapsed)
"""


def run_trial_subprocess(df_path, use_autolineage):
    """Run a single pipeline trial in a fresh Python subprocess.

    Why subprocesses? AutoLineage hooks patch framework classes on import.
    Once patched in a process, you cannot cleanly un-patch for the next trial.
    Running each trial in a subprocess guarantees a clean environment.

    Returns wall-clock time in seconds, or None on failure.
    """
    script = _build_trial_script(df_path, use_autolineage)
    script_path = SCRIPT_DIR / "_trial_tmp.py"
    script_path.write_text(script)
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            print(f"    TRIAL FAILED (code {result.returncode}):")
            print(f"    stdout tail: {result.stdout[-400:]}")
            print(f"    stderr tail: {result.stderr[-400:]}")
            return None
        lines = [ln.strip() for ln in result.stdout.strip().splitlines() if ln.strip()]
        elapsed = float(lines[-1])
        return elapsed
    finally:
        script_path.unlink(missing_ok=True)


def sample_at_size(full_df: pd.DataFrame, size: int) -> pd.DataFrame:
    """Produce a dataframe of the requested size.

    For sizes <= len(full_df), subsample with stratification on Class.
    For sizes > len(full_df), upsample with replacement.
    """
    if size <= len(full_df):
        pos = full_df[full_df["Class"] == 1]
        neg = full_df[full_df["Class"] == 0]
        frac = size / len(full_df)
        pos_n = max(2, int(len(pos) * frac))
        neg_n = size - pos_n
        sampled = pd.concat([
            pos.sample(n=pos_n, random_state=42),
            neg.sample(n=neg_n, random_state=42),
        ])
        return sampled.sample(frac=1, random_state=42).reset_index(drop=True)
    else:
        return full_df.sample(n=size, replace=True, random_state=42).reset_index(drop=True)


def main():
    print("=" * 70)
    print("AutoLineage Paper 1 — Scaling Experiment")
    print("=" * 70)

    if not DATA_PATH.exists():
        print(f"\n[ERROR] Dataset not found at {DATA_PATH}")
        print("Download from: https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud")
        print(f"Then place creditcard.csv in {DATA_PATH.parent}")
        sys.exit(1)

    print(f"\nLoading dataset from {DATA_PATH}...")
    full_df = pd.read_csv(DATA_PATH)
    print(f"  Loaded {len(full_df):,} rows, {full_df.shape[1]} columns")
    print(f"  Class distribution: {dict(full_df['Class'].value_counts())}")

    # Pre-sample all sizes and pickle them to disk
    sampled_paths = {}
    tmp_dir = SCRIPT_DIR / "_tmp_samples"
    tmp_dir.mkdir(exist_ok=True)
    for size in SIZES:
        df_sample = sample_at_size(full_df, size)
        pickle_path = tmp_dir / f"sample_{size}.pkl"
        df_sample.to_pickle(pickle_path)
        sampled_paths[size] = pickle_path
        print(f"  Pre-sampled {size:,} rows -> {pickle_path.name}")

    results = []

    for size in SIZES:
        print(f"\n{'=' * 60}")
        print(f"Dataset size: {size:,} rows")
        print(f"{'=' * 60}")

        # Baseline trials
        print(f"  Baseline ({N_TRIALS} trials)...")
        baseline_times = []
        for t in range(N_TRIALS):
            elapsed = run_trial_subprocess(sampled_paths[size], use_autolineage=False)
            if elapsed is None:
                print(f"    [skipping failed trial]")
                continue
            baseline_times.append(elapsed)
            print(f"    trial {t + 1}/{N_TRIALS}: {elapsed:.2f}s")

        # AutoLineage trials
        print(f"  With AutoLineage ({N_TRIALS} trials)...")
        hooked_times = []
        for t in range(N_TRIALS):
            elapsed = run_trial_subprocess(sampled_paths[size], use_autolineage=True)
            if elapsed is None:
                print(f"    [skipping failed trial]")
                continue
            hooked_times.append(elapsed)
            print(f"    trial {t + 1}/{N_TRIALS}: {elapsed:.2f}s")

        if not baseline_times or not hooked_times:
            print(f"  [WARNING] Insufficient trials at size {size:,}, skipping")
            continue

        baseline_mean = float(np.mean(baseline_times))
        baseline_std = float(np.std(baseline_times, ddof=1)) if len(baseline_times) > 1 else 0.0
        hooked_mean = float(np.mean(hooked_times))
        hooked_std = float(np.std(hooked_times, ddof=1)) if len(hooked_times) > 1 else 0.0
        overhead_pct = 100.0 * (hooked_mean - baseline_mean) / baseline_mean

        results.append({
            "size": size,
            "baseline_mean_s": baseline_mean,
            "baseline_std_s": baseline_std,
            "autolineage_mean_s": hooked_mean,
            "autolineage_std_s": hooked_std,
            "overhead_pct": overhead_pct,
            "n_trials_baseline": len(baseline_times),
            "n_trials_autolineage": len(hooked_times),
        })

        print(f"\n  Baseline:    {baseline_mean:.2f} ± {baseline_std:.2f} s  (n={len(baseline_times)})")
        print(f"  AutoLineage: {hooked_mean:.2f} ± {hooked_std:.2f} s  (n={len(hooked_times)})")
        print(f"  Overhead:    {overhead_pct:.1f}%")

    # Clean up temp samples
    for path in sampled_paths.values():
        path.unlink(missing_ok=True)
    try:
        tmp_dir.rmdir()
    except OSError:
        pass

    if not results:
        print("\n[ERROR] No successful trials. Aborting.")
        sys.exit(1)

    # Save raw data
    results_df = pd.DataFrame(results)
    results_df.to_csv(RESULTS_CSV, index=False)
    print(f"\n[OK] Wrote {RESULTS_CSV}")

    # ==== FIGURE 2: SCALING PLOT ====
    fig, ax = plt.subplots(figsize=(6, 3.8))

    ax.errorbar(
        results_df["size"],
        results_df["baseline_mean_s"],
        yerr=results_df["baseline_std_s"],
        marker="o", markersize=7, linewidth=1.5,
        capsize=4, label="Baseline",
        color="#333333",
    )
    ax.errorbar(
        results_df["size"],
        results_df["autolineage_mean_s"],
        yerr=results_df["autolineage_std_s"],
        marker="s", markersize=7, linewidth=1.5,
        capsize=4, label="With AutoLineage",
        color="#8b2a17",
    )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Dataset size (rows)")
    ax.set_ylabel("Wall-clock time (s)")
    ax.legend(loc="lower right", frameon=False)
    ax.grid(True, which="both", linestyle=":", linewidth=0.5, alpha=0.5)

    # Inset: overhead percentage
    ax_inset = fig.add_axes([0.22, 0.58, 0.30, 0.28])
    ax_inset.plot(
        results_df["size"],
        results_df["overhead_pct"],
        marker="D", markersize=5, linewidth=1.4,
        color="#8b2a17",
    )
    ax_inset.set_xscale("log")
    ax_inset.set_xlabel("Rows", fontsize=8)
    ax_inset.set_ylabel("Overhead (%)", fontsize=8)
    ax_inset.tick_params(labelsize=7)
    ax_inset.set_ylim(0, max(15, results_df["overhead_pct"].max() + 3))
    ax_inset.grid(True, linestyle=":", linewidth=0.4, alpha=0.5)
    ax_inset.set_title("Relative overhead", fontsize=9)

    plt.savefig(FIGURE_PATH_PDF)
    plt.savefig(FIGURE_PATH_PNG)
    plt.close()
    print(f"[OK] Wrote {FIGURE_PATH_PDF}")
    print(f"[OK] Wrote {FIGURE_PATH_PNG}")

    # ==== PAPER-READY TABLE ====
    print("\n\n" + "=" * 72)
    print("SCALING RESULTS — paste into paper text and Figure 2 caption:")
    print("=" * 72)
    print(f"{'Size':>10} | {'Baseline (s)':>18} | {'AutoLineage (s)':>20} | {'Overhead':>10}")
    print("-" * 72)
    for r in results:
        size_str = f"{r['size']:,}"
        baseline_str = f"{r['baseline_mean_s']:.2f} ± {r['baseline_std_s']:.2f}"
        hooked_str = f"{r['autolineage_mean_s']:.2f} ± {r['autolineage_std_s']:.2f}"
        overhead_str = f"{r['overhead_pct']:.1f}%"
        print(f"{size_str:>10} | {baseline_str:>18} | {hooked_str:>20} | {overhead_str:>10}")
    print("=" * 72)

    min_oh = results_df["overhead_pct"].min()
    max_oh = results_df["overhead_pct"].max()
    print(f"\nFigure 2 caption update: 'Overhead is bounded between "
          f"{min_oh:.1f}% and {max_oh:.1f}% across three orders of magnitude.'")


if __name__ == "__main__":
    main()
