"""The held-out split. One run, after development stops.

``LOCKED`` stays true until the dev set is frozen. The numbers this file
prints, whatever they are, are the ones that go in the paper.
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
OUT = ROOT / "benchmarks" / "real" / "heldout_results"

# The one held-out run is in heldout_results/. Leave this true.
LOCKED = True


def main(argv=None) -> int:
    if LOCKED:
        sys.stderr.write(
            "Held-out is locked. It runs once, after the library stops changing "
            "on the dev set. This invocation did not score any pipeline.\n"
        )
        return 2
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    slots = [s for s in manifest.get("heldout", []) if s.get("scored") and s.get("qualified_run")]
    if not slots:
        sys.stderr.write("No qualified held-out slots.\n")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    cases = []
    for slot in slots:
        script = _materialise(slot)
        if script is None:
            print(f"skip {slot.get('slot')}: script is not in the cache", flush=True)
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
            result["repo"] = slot.get("repo")
            result["path"] = slot.get("path")
            cases.append(result)
            dest.write_text(json.dumps(result, indent=2), encoding="utf-8")
    summary = summarize(cases)
    summary["scripts"] = [s.get("slot") for s in slots]
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("Held-out summary. These rates go in the paper.")
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
