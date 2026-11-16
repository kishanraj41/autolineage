"""Command line for the incident checks.

``autolineage baseline script.py -o baseline.json`` records a good run.
``autolineage check script.py --baseline baseline.json`` exits non-zero
when a check fails, so a CI job can run it. Arguments after ``--`` are
passed to the script.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .checks import capture_run, evaluate, load_contract, load_run, save_run

EXIT_VIOLATION = 1
EXIT_ERROR = 2


def main(argv=None) -> int:
    """Run a baseline capture or a check. Returns the process exit code."""
    argv = list(sys.argv[1:] if argv is None else argv)
    script_args = []
    if "--" in argv:
        split = argv.index("--")
        argv, script_args = argv[:split], argv[split + 1:]

    parser = argparse.ArgumentParser(
        prog="autolineage",
        epilog="Arguments after -- are passed to the script.",
    )
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
        records, error = capture_run(args.script, contract, script_args)
        if error:
            print(error, file=sys.stderr)
            return EXIT_ERROR
        if not records:
            return _nothing_recorded(args.script)
        save_run(args.output, records, contract,
                 root=str(Path(args.script).resolve().parent))
        print(f"wrote {args.output} ({len(records)} records)")
        return 0

    try:
        baseline_records, saved_contract = load_run(args.baseline)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"could not read baseline: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if not baseline_records:
        print(f"baseline {args.baseline} holds no records; record it again",
              file=sys.stderr)
        return EXIT_ERROR
    if contract is None:
        contract = saved_contract
    records, error = capture_run(args.script, contract, script_args)
    if error:
        print(error, file=sys.stderr)
        return EXIT_ERROR
    if not records:
        return _nothing_recorded(args.script)
    violations = evaluate(records, baseline_records, contract)
    for item in violations:
        print(item.format())
    if violations:
        print(f"{len(violations)} violation(s)")
        return EXIT_VIOLATION
    print(f"no violations ({len(records)} records)")
    return 0


def _nothing_recorded(script: str) -> int:
    """A run with no records cannot pass: there is nothing to compare."""
    print(
        f"{script} ran and no pandas or scikit-learn call was recorded, "
        "so there is nothing to check",
        file=sys.stderr,
    )
    return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
