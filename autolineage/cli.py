"""Command line for the incident checks.

``autolineage baseline script.py -o baseline.json`` records a good run.
``autolineage check script.py --baseline baseline.json`` exits non-zero
when a check fails, so a CI job can run it.
"""

from __future__ import annotations

import argparse
import sys

from .checks import capture_run, evaluate, load_contract, load_run, save_run


def main(argv=None) -> int:
    """Run a baseline capture or a check. Returns the process exit code."""
    parser = argparse.ArgumentParser(prog="autolineage")
    sub = parser.add_subparsers(dest="command", required=True)

    baseline = sub.add_parser("baseline", help="record a run to compare against")
    baseline.add_argument("script")
    baseline.add_argument("-o", "--output", required=True)
    baseline.add_argument("--contract", help="JSON file of declared columns")

    check = sub.add_parser("check", help="compare a run with a saved baseline")
    check.add_argument("script")
    check.add_argument("--baseline", required=True)
    check.add_argument("--contract", help="JSON file of declared columns")

    args = parser.parse_args(argv)
    contract = load_contract(args.contract) if args.contract else None
    if args.command == "baseline":
        records, error = capture_run(args.script, contract)
        if error:
            print(error, file=sys.stderr)
            return 2
        save_run(args.output, records, contract)
        print(f"wrote {args.output} ({len(records)} records)")
        return 0

    try:
        baseline_records, saved_contract = load_run(args.baseline)
    except (OSError, ValueError, KeyError) as exc:
        print(f"could not read baseline: {exc}", file=sys.stderr)
        return 2
    if contract is None:
        contract = saved_contract
    records, error = capture_run(args.script, contract)
    if error:
        print(error, file=sys.stderr)
        return 2
    violations = evaluate(records, baseline_records, contract)
    for item in violations:
        print(item.format())
    if violations:
        print(f"{len(violations)} violation(s)")
        return 1
    print("no violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
