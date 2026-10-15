"""Run fault mutations on the development split only.

Refuses a manifest slot marked held-out. That split is run once, later,
by run_heldout.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.real.mutate import FAULTS
from benchmarks.real.run_case import evaluate
from benchmarks.real.score import summarize

MANIFEST = ROOT / "benchmarks" / "real" / "manifest.json"
OUT = ROOT / "benchmarks" / "real" / "dev_results"


def main(argv=None) -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    slots = [s for s in manifest.get("dev", []) if s.get("scored")]
    held = [s for s in manifest.get("heldout", []) if s.get("scored")]
    if any(s.get("role") == "heldout" for s in slots):
        sys.exit("refusing: a held-out slot was passed to the dev runner")
    if not slots:
        print("No scored dev slots in the manifest yet. Held-out is not run from here.")
        if held:
            print(f"{len(held)} held-out slots are locked and were not executed.")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    cases = []
    for slot in slots:
        script = _materialise(slot)
        if script is None:
            print(f"skip {slot.get('slot')}: script is not in the cache")
            continue
        for fault in FAULTS:
            dest = OUT / f"{slot['slot']}-{fault}.json"
            if dest.is_file():
                cases.append(json.loads(dest.read_text(encoding="utf-8")))
                print(f"resume {slot['slot']} {fault}", flush=True)
                continue
            print(f"score {slot['slot']} {fault}", flush=True)
            result = evaluate(script, fault, case_id=f"{slot['slot']}:{fault}")
            result["slot"] = slot["slot"]
            cases.append(result)
            dest.write_text(json.dumps(result, indent=2), encoding="utf-8")
    summary = summarize(cases)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("Dev summary only. Do not put these rates in the paper.")
    return 0


def _materialise(slot: dict):
    repo = slot["repo"].replace("/", "__")
    staged = slot.get("staged_script") or Path(slot.get("path", "")).name
    candidate = ROOT / "benchmarks" / "real" / "cache" / repo / slot.get("path", "") / staged
    if candidate.is_file():
        return candidate
    return None


if __name__ == "__main__":
    sys.exit(main())
