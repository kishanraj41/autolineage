"""Run one script, plant one fault, and score it.

Held-out slots are not accepted. ``run_heldout.py`` is the only entry
point for that split, and it stays locked until development is finished.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from benchmarks.real.mutate import FAULTS, bump_random_state, mutate
from benchmarks.real.score import score_case

ROOT = Path(__file__).resolve().parents[2]
ENTRY = Path(__file__).resolve().parent / "entry.py"


def evaluate(script: Path, fault: str, *, case_id: str = None, timeout: int = 600) -> dict:
    """Score ``fault`` on ``script``. Does not write a published rate."""
    script = Path(script).resolve()
    case_id = case_id or f"{script.name}:{fault}"
    source = script.read_text(encoding="utf-8")
    mutation = mutate(source, fault)
    if mutation is None:
        return {"fault": fault, "status": "not_applicable", "mutated_line": None,
                "detected": None, "top1": None, "top3": None}

    # The mutated copy sits beside the original so Path(__file__) still
    # finds the dataset. It is removed before this function returns.
    mutated_path = script.with_name(script.stem + ".mutated" + script.suffix)
    rerun_path = script.with_name(script.stem + ".rerun" + script.suffix)
    try:
        mutated_path.write_text(mutation.source, encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix="al-real-") as tmp:
            work = Path(tmp)
            clean_fp = work / "baseline.json"
            clean = _run(script, work, timeout, tag="clean", save_fingerprint=clean_fp)
            mutated_report = _run(mutated_path, work, timeout, tag="mutated", baseline=clean_fp)
            rerun_source = bump_random_state(source)
            if rerun_source is None:
                fp_path = script
            else:
                rerun_path.write_text(rerun_source, encoding="utf-8")
                fp_path = rerun_path
            rerun = _run(fp_path, work, timeout, tag="rerun", baseline=clean_fp)
            plain = _run(script, work, timeout, tag="plain", hooks=False)
            return score_case(
                fault=fault,
                mutated_line=mutation.line,
                clean_script=str(script),
                mutated_script=str(mutated_path),
                case_id=case_id,
                clean=clean,
                mutated=mutated_report,
                unmutated_rerun=rerun,
                wall_without_hooks_s=plain.get("wall_s"),
                mutated_source=mutation.source,
            )
    finally:
        mutated_path.unlink(missing_ok=True)
        rerun_path.unlink(missing_ok=True)


def _kill_tree(pid: int) -> None:
    """Kill a script and the workers it spawned.

    On Windows, ``subprocess.run(..., timeout=)`` kills the child and then
    waits for pipes the grandchildren still hold, so a timed-out pool never
    returns. Killing the tree closes those pipes.
    """
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True, check=False,
        )
        return
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _crash(error: str, wall_s) -> dict:
    return {"status": "crash", "error": error, "wall_s": wall_s,
            "metrics": {}, "records": [], "anomalies": [], "ranking": []}


def _run(script: Path, work: Path, timeout: int, *, tag: str, save_fingerprint: Path = None,
         baseline: Path = None, hooks: bool = True) -> dict:
    report = work / f"{tag}.json"
    cmd = [sys.executable, str(ENTRY), "--script", str(script), "--report", str(report),
           "--hooks", "1" if hooks else "0"]
    if save_fingerprint is not None:
        cmd.extend(["--save-fingerprint", str(save_fingerprint)])
    if baseline is not None and baseline.exists():
        cmd.extend(["--baseline", str(baseline)])
    env = os.environ.copy()
    # Qualification already forced this. Scoring did not, so a script that
    # calls plt.show() paid GUI startup inside the wall-clock overhead.
    env["MPLBACKEND"] = "Agg"
    proc = subprocess.Popen(
        cmd, cwd=str(script.parent), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=(os.name != "nt"), env=env,
    )
    try:
        proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc.pid)
        try:
            proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
        if report.is_file():
            try:
                return json.loads(report.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return _crash("timeout", float(timeout))
    if not report.is_file():
        return _crash("no report", None)
    return json.loads(report.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Score one fault on one script (dev only).")
    parser.add_argument("script", type=Path)
    parser.add_argument("fault", choices=FAULTS)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args(argv)
    result = evaluate(args.script, args.fault, timeout=args.timeout)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
