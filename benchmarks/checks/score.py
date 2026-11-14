"""Score the eight cases in PROTOCOL.md. Run this only after that file is committed."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autolineage.checks import capture_run, evaluate, load_contract  # noqa: E402

CASES = [
    ("repro_003", "row_conservation", None),
    ("repro_001", "null_rate_after_coerce", None),
    ("repro_004", "monotonic_cumulative", "repro_004.json"),
    ("repro_002", "row_conservation", None),
    ("sf002_truncation", "row_conservation", None),
    ("sf018_merge_drop", "row_conservation", None),
    ("sf036_volume", "freshness_and_volume", "sf036_volume.json"),
    ("sf024_dst", "unique_keys_timestamps", "sf024_dst.json"),
]


def fault_line(path: Path) -> int:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if "# fault" in line:
            return number
    raise SystemExit(f"{path} has no # fault line")


def score_case(case_id: str, check: str, contract_name: str | None) -> dict:
    case_dir = ROOT / "benchmarks" / "checks" / "cases"
    contract = None
    if contract_name:
        contract = load_contract(str(ROOT / "benchmarks" / "checks" / "contracts" / contract_name))
    baseline_script = case_dir / f"{case_id}_baseline.py"
    fault_script = case_dir / f"{case_id}_fault.py"
    baseline, base_error = capture_run(str(baseline_script), contract)
    current, fault_error = capture_run(str(fault_script), contract)
    if base_error or fault_error:
        return {
            "id": case_id, "check": check, "result": "error",
            "localized": False, "error": base_error or fault_error,
        }
    aimed = [item for item in evaluate(current, baseline, contract) if item.check == check]
    line = fault_line(fault_script)
    localized = any(item.source_line == line for item in aimed)
    return {
        "id": case_id,
        "check": check,
        "result": "caught" if aimed else "missed",
        "localized": localized,
        "fault_line": line,
        "lines": [item.source_line for item in aimed],
        "messages": [item.message for item in aimed],
    }


def main() -> int:
    rows = [score_case(*case) for case in CASES]
    out = ROOT / "benchmarks" / "checks" / "results.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"{'case':<20} {'check':<24} {'result':<8} localized")
    for row in rows:
        print(f"{row['id']:<20} {row['check']:<24} {row['result']:<8} {row['localized']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
