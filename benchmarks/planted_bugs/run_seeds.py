"""Run the five planted-bug cases across several seeds and summarise.

Each (case, seed) pair runs the healthy pipeline and then the buggy one in
fresh processes, exactly as run_all.sh does for seed 0. The seed controls
the synthetic data, the train/test split and the sampling step.

    python run_seeds.py            # seeds 0-4
    python run_seeds.py 0 1 2      # any seeds

Writes results_multiseed.json and prints a Markdown summary table.
"""
import json
import os
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = ["filter", "join", "encoding", "leakage", "type"]
SEEDS = [int(s) for s in sys.argv[1:]] or [0, 1, 2, 3, 4]


def run(case, mode, seed):
    env = dict(os.environ, PYTHONHASHSEED="0")
    out = subprocess.run([sys.executable, "pipeline.py", case, mode, str(seed)],
                         cwd=HERE, env=env, capture_output=True, text=True)
    lines = [l for l in out.stdout.splitlines() if l.startswith("{")]
    if out.returncode != 0 or not lines:
        raise RuntimeError(f"{case}/{mode}/seed {seed} failed:\n{out.stderr[-2000:]}")
    return json.loads(lines[-1])


def mean_sd(xs):
    return statistics.mean(xs), (statistics.stdev(xs) if len(xs) > 1 else 0.0)


rows = []
for case in CASES:
    for seed in SEEDS:
        base = run(case, "baseline", seed)
        bug = run(case, "buggy", seed)
        rc = bug.get("root_cause") or {}
        rows.append({
            "case": case, "seed": seed,
            "base_f1": base["base_f1"], "buggy_f1": bug["buggy_f1"],
            "detected": bug["n_anom"] > 0,
            "root_op": rc.get("root_op"), "impact": rc.get("impact"),
            "expected_op": bug["expected_op"],
            "exact": rc.get("root_op") == bug["expected_op"],
        })
        try:
            os.remove(os.path.join(HERE, f"fp_{case}_s{seed}.json"))
        except FileNotFoundError:
            pass
        print(f"{case:9s} seed {seed}: {rc.get('root_op')!s:12s} "
              f"(impact {rc.get('impact')}) expected {bug['expected_op']}", file=sys.stderr)

with open(os.path.join(HERE, "results_multiseed.json"), "w") as fh:
    json.dump({"seeds": SEEDS, "runs": rows}, fh, indent=2)

n = len(SEEDS)
print(f"| # | Bug category | Baseline F1 (mean ± sd) | Buggy F1 (mean ± sd) | Detected | Exact localization | Impact (mean ± sd) |")
print("|---|---|---|---|---|---|---|")
for i, case in enumerate(CASES, 1):
    r = [x for x in rows if x["case"] == case]
    bf, bs = mean_sd([x["base_f1"] for x in r])
    gf, gs = mean_sd([x["buggy_f1"] for x in r])
    imps = [x["impact"] for x in r if x["impact"] is not None]
    im, isd = mean_sd(imps) if imps else (float("nan"), 0.0)
    print(f"| {i} | {case} | {bf:.3f} ± {bs:.3f} | {gf:.3f} ± {gs:.3f} | "
          f"{sum(x['detected'] for x in r)}/{n} | {sum(x['exact'] for x in r)}/{n} | {im:.2f} ± {isd:.2f} |")
tot = len(rows)
print(f"\nDetected {sum(x['detected'] for x in rows)}/{tot}; exact {sum(x['exact'] for x in rows)}/{tot}.")
