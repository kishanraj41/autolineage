# Check-suite notes

Moved out of `docs/` on 21 November 2026. These notes are not a result and are not linked from the README. The cases are author-written scripts. The held-out study was not part of this run.

Protocol: `benchmarks/checks/PROTOCOL.md`, committed in `4fc0270` before the run.

Scored with `python benchmarks/checks/score.py`. Eight cases. A case is caught when the aimed check reports a violation, and localized when that violation names the line marked `# fault`.

| Case | Aimed check | Result | Localized to the fault line |
|---|---|---|---|
| repro_003 merge fan-out | row_conservation | caught | yes. `16 -> 20`, baseline `16 -> 16` |
| repro_001 coerce to null | null_rate_after_coerce | caught | yes. null fraction 0.200, baseline 0.000 |
| repro_004 cumulative column | monotonic_cumulative | caught | yes. `Vaccinated_1st` decreased |
| repro_002 truncated running total | row_conservation | missed | no |
| sf002 row-cap truncation | row_conservation | caught | yes. `100 -> 60`, baseline `100 -> 100` |
| sf018 merge drop | row_conservation | caught | yes. `4 -> 2`, baseline `4 -> 4` |
| sf036 per-source volume | freshness_and_volume | caught | yes. `lab_b` has 5 rows, baseline 100 |
| sf024 DST hour shift | unique_keys_timestamps | missed | no |

6 caught, all 6 localized. 2 missed.

The table is the run on 0.8.0. The same eight scripts and three contracts, unedited, were scored again on the build that runs scripts as `__main__`, matches steps by alignment, and adds the load rule. That run wrote an identical `results.json`.

## Misses

**repro_002.** The running total is truncated with `int(x * 1000) / 1000`. There is no pandas call, so the trace has no row counts to compare. `row_conservation` has nothing to fail.

**sf024.** The timestamps move back one hour at the DST boundary and stay unique and increasing. `unique_keys_timestamps` fails on duplicate keys and duplicate timestamps. A shift that does not repeat a value is invisible to it. The duplicate-hour failures (SF-025, SF-028, SF-029, SF-031) are the ones this check is built for. A unit test covers a repeated key. This case is the one the check does not see.
