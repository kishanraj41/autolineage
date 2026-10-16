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
import time
from pathlib import Path

from benchmarks.real.mutate import FAULTS, bump_random_state, mutate
from benchmarks.real.score import score_case

ROOT = Path(__file__).resolve().parents[2]
ENTRY = Path(__file__).resolve().parent / "entry.py"


def evaluate(script: Path, fault: str, *, case_id: str = None, timeout: int = 600,
             keep_dir: Path = None) -> dict:
    """Score ``fault`` on ``script``. Does not write a published rate."""
    script = Path(script).resolve()
    case_id = case_id or f"{script.name}:{fault}"
    source = script.read_text(encoding="utf-8")
    mutation = mutate(source, fault)
    if mutation is None:
        return {"fault": fault, "status": "not_applicable", "mutated_line": None,
                "detected": None, "top1": None, "top3": None}

    # The mutated copy sits beside the original so Path(__file__) still
    # finds the dataset. A copy is kept under ``keep_dir`` when that path
    # is set. The sibling next to the original is removed either way.
    mutated_path = script.with_name(script.stem + ".mutated" + script.suffix)
    rerun_path = script.with_name(script.stem + ".rerun" + script.suffix)
    try:
        mutated_path.write_text(mutation.source, encoding="utf-8")
        with tempfile.TemporaryDirectory(prefix="al-real-") as tmp:
            work = Path(tmp)
            clean_fp = work / "baseline.json"
            clean_attempts = [_run(
                script, work, timeout, tag="clean", save_fingerprint=clean_fp,
                log_dir=keep_dir, log_name=case_id,
            )]
            if clean_attempts[0].get("status") != "ok":
                clean_attempts.append(_run(
                    script, work, timeout, tag="clean", save_fingerprint=clean_fp,
                    log_dir=keep_dir, log_name=case_id, attempt=2,
                ))
            clean = clean_attempts[-1]
            mutated_report = _run(
                mutated_path, work, timeout, tag="mutated", baseline=clean_fp,
                log_dir=keep_dir, log_name=case_id,
            )
            rerun_source = bump_random_state(source)
            if rerun_source is None:
                fp_path = script
            else:
                rerun_path.write_text(rerun_source, encoding="utf-8")
                fp_path = rerun_path
            rerun = _run(
                fp_path, work, timeout, tag="rerun", baseline=clean_fp,
                log_dir=keep_dir, log_name=case_id,
            )
            plain = _run(
                script, work, timeout, tag="plain", hooks=False,
                log_dir=keep_dir, log_name=case_id,
            )
            result = score_case(
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
            result["process_logs"] = {
                "clean": [_process_log(item) for item in clean_attempts],
                "mutated": [_process_log(mutated_report)],
                "rerun": [_process_log(rerun)],
                "plain": [_process_log(plain)],
            }
            return result
    finally:
        if keep_dir is not None and mutated_path.is_file():
            dest_dir = Path(keep_dir)
            dest_dir.mkdir(parents=True, exist_ok=True)
            name = f"{(case_id or script.stem).replace(':', '-')}.py"
            (dest_dir / name).write_text(
                mutated_path.read_text(encoding="utf-8"), encoding="utf-8",
            )
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


def _process_log(report: dict) -> dict:
    return {
        "status": report.get("status"),
        "error": report.get("error"),
        "exit_code": report.get("exit_code"),
        "subprocess_wall_s": report.get("subprocess_wall_s"),
        "stderr": report.get("stderr") or "",
    }


def _attach_process(report: dict, *, stderr: str, exit_code, wall_s: float,
                    log_dir: Path = None, log_name: str = None, tag: str = "") -> dict:
    text = stderr or ""
    report["stderr"] = text[-16000:]
    report["exit_code"] = exit_code
    report["subprocess_wall_s"] = wall_s
    if log_dir is not None and log_name:
        dest_dir = Path(log_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        stem = log_name.replace(":", "-")
        (dest_dir / f"{stem}-{tag}.stderr.txt").write_text(text, encoding="utf-8")
    return report


def _run(script: Path, work: Path, timeout: int, *, tag: str, save_fingerprint: Path = None,
         baseline: Path = None, hooks: bool = True, log_dir: Path = None,
         log_name: str = None, attempt: int = 1) -> dict:
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
    started = time.perf_counter()
    proc = subprocess.Popen(
        cmd, cwd=str(script.parent), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=(os.name != "nt"), env=env,
    )
    log_tag = tag if attempt == 1 else f"{tag}-retry"
    try:
        _out, err = proc.communicate(timeout=timeout)
        exit_code = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired:
        _kill_tree(proc.pid)
        try:
            _out, err = proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            _out, err = proc.communicate()
        exit_code = proc.returncode
        timed_out = True
    wall_s = time.perf_counter() - started
    if timed_out:
        loaded = None
        if report.is_file():
            try:
                loaded = json.loads(report.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                loaded = None
        loaded = loaded if loaded is not None else _crash("timeout", float(timeout))
        if loaded.get("status") == "ok":
            loaded = _crash("timeout", loaded.get("wall_s"))
        return _attach_process(
            loaded, stderr=err or "", exit_code=exit_code, wall_s=wall_s,
            log_dir=log_dir, log_name=log_name, tag=log_tag,
        )
    if not report.is_file():
        loaded = _crash("no report", wall_s)
    else:
        loaded = json.loads(report.read_text(encoding="utf-8"))
    return _attach_process(
        loaded, stderr=err or "", exit_code=exit_code, wall_s=wall_s,
        log_dir=log_dir, log_name=log_name, tag=log_tag,
    )


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
