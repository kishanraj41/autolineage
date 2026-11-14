# Check benchmark protocol

Frozen 2026-11-13, before the run. This protocol scores the five checks in `autolineage.checks`. It does not touch `benchmarks/real/` and it does not change the held-out study.

## What is scored

Eight scripts. Four follow the corpus reproductions. Four are new and named after one corpus row each. Every fault script has exactly one line marked `# fault`. That line is the call the check is supposed to name.

| Case | Aimed check | Corpus ids | What the fault does |
|---|---|---|---|
| `repro_003` | `row_conservation` | SF-018, SF-022 | Left merge against a key that is duplicated on the right |
| `repro_001` | `null_rate_after_coerce` | SF-001, SF-020, SF-021 | `to_datetime(errors="coerce")` on a column that contains unparseable values |
| `repro_004` | `monotonic_cumulative` | SF-016 | A column declared cumulative decreases |
| `repro_002` | `row_conservation` | SF-004 | A running total truncated to three decimals, with no pandas call |
| `sf002_truncation` | `row_conservation` | SF-002 | `head` keeps 60 of 100 rows |
| `sf018_merge_drop` | `row_conservation` | SF-018 | Inner merge drops rows the baseline left merge kept |
| `sf036_volume` | `freshness_and_volume` | SF-019, SF-036 | One source falls from 100 rows to 5; the max date stays the same |
| `sf024_dst` | `unique_keys_timestamps` | SF-024, SF-025, SF-028, SF-029, SF-031 | Timestamps shift by one hour at a DST boundary and stay unique |

`repro_001` uses the coerce-then-null mechanism. It does not name the repository or the person from corpus row SF-001.

## How a case is run

1. Run `cases/<id>_baseline.py` with `autolineage baseline`, the case contract, and a fresh output file.
2. Run `cases/<id>_fault.py` with `autolineage check` against that file and the same contract.
3. Do not edit a script after looking at a result. A change to a script, a tolerance, or a contract is a new protocol and a new run.

Tolerances are the ones in `autolineage.checks`: row-change rate 0.01, null-fraction increase 0.01, source-volume band 0.20 unless the contract sets `volume_band`. A date is stale only when the run's max date is strictly earlier than the baseline's.

## How a case is counted

Look only at violations whose check is the aimed check.

- **Caught** — at least one such violation.
- **Localized** — one of those violations names the `# fault` line.
- **Missed** — no such violation.

Caught and localized are separate. A miss is reported, not repaired, in this run.

## What is not scored

The held-out pipeline-call coverage stays the published 0.29. Dev-script coverage is not a result of this protocol. Polars, Spark, and any repair of a failing check are out of scope.
