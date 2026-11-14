# unique_keys_timestamps

A contract lists keys and one time index. The check fails when a recorded frame contains a duplicate value in any of them.

```json
{"keys": ["animal_id"], "time_index": "timestamp"}
```

| Corpus id | Incident |
|---|---|
| SF-024 | Pirate Weather reused one timezone object and added 24 hours, so each local midnight drifted to 23:00 after a DST change. The timestamps stayed unique. |
| SF-025 | pvanalytics repeated the 03:00 hour at a DST fallback. The index was duplicated and not monotonic. |
| SF-028 | An Elasticsearch `date_histogram` emitted two `03:00` buckets for the DST overlap hour. |
| SF-029 | TimescaleDB `time_bucket_gapfill` emitted a duplicated `01:00` UTC bucket, one of them null, at the Europe/Paris change. |
| SF-031 | A dbt uniqueness test caught about 100 duplicated SLA events after a DST change doubled a schedule. |

A shift that keeps every timestamp unique, which is what SF-024 did, does not fail this check. Duplicate hours do.
