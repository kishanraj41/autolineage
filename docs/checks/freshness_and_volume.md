# freshness_and_volume

A contract names a date column and, optionally, a source column.

The date fails when the latest value in the run is strictly earlier than the latest value in the baseline. An equal date is a rerun of the same day, not a failure.

A source fails when its row count moves by more than `volume_band` (default 0.20) from that source's count in the baseline. A source present in the baseline and absent now is a count of zero.

```json
{"date_column": "date", "source_column": "source", "volume_band": 0.2}
```

| Corpus id | Incident |
|---|---|
| SF-019 | microCOVID kept serving week-old risk numbers after an upstream feed stopped sending one locale and processing stopped. |
| SF-036 | California's CalREDIE backloged about 300,000 COVID test results after a crash workaround and an expired lab certificate. Published counts kept moving. |

The report names the recorded call that carried the date or the per-source counts.
