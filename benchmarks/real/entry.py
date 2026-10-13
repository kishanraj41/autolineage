"""Run one script and write a JSON report. Used by run_case.py.

The hooks are installed before the script loads, so its imports of pandas
and scikit-learn are already patched. Line numbers stay the script's own:
nothing is prepended to the file.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--baseline", default=None)
    parser.add_argument("--save-fingerprint", default=None)
    parser.add_argument("--hooks", choices=("0", "1"), default="1")
    args = parser.parse_args(argv)

    script = Path(args.script).resolve()
    report_path = Path(args.report)
    hooks = args.hooks == "1"
    if hooks:
        import autolineage.auto  # noqa: F401
        from autolineage.auto import get_tracker
        from autolineage.core.analyzer import LineageAnalyzer

    sys.path.insert(0, str(script.parent))
    started = time.perf_counter()
    status = "ok"
    error = ""
    try:
        import runpy
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:
        if exc.code not in (0, None):
            status = "crash"
            error = f"SystemExit {exc.code}"
    except Exception:
        status = "crash"
        error = traceback.format_exc(limit=8)
    wall_s = time.perf_counter() - started

    report = {"status": status, "error": error, "wall_s": wall_s,
              "metrics": {}, "records": [], "anomalies": [], "ranking": []}
    if hooks and status == "ok":
        tracker = get_tracker()
        analyzer = LineageAnalyzer(tracker)
        if args.save_fingerprint:
            analyzer.save_fingerprint(args.save_fingerprint, append=False)
        if args.baseline:
            analyzer.load_baseline(args.baseline)
            report["anomalies"] = [a.to_dict() for a in analyzer.detect_anomalies()]
            report["ranking"] = _jsonable(analyzer.ranked_causes())
        fp = analyzer.fingerprint()
        report["metrics"] = {
            name: value for name, value in fp.metrics.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        report["records"] = [_record(rec) for rec in tracker.records]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report), encoding="utf-8")
    return 0


def _record(rec) -> dict:
    meta = rec.metadata if isinstance(rec.metadata, dict) else {}
    return {
        "operation": rec.operation,
        "category": rec.category,
        "rows_before": rec.rows_before,
        "rows_after": rec.rows_after,
        "duration_ms": rec.duration_ms,
        "source_file": meta.get("source_file"),
        "source_line": meta.get("source_line"),
    }


def _jsonable(ranking):
    out = []
    for entry in ranking:
        item = dict(entry)
        item["evidence"] = {
            key: list(value) if isinstance(value, set) else value
            for key, value in (entry.get("evidence") or {}).items()
        }
        out.append(item)
    return out


if __name__ == "__main__":
    sys.exit(main())
