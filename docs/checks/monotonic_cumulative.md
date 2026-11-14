# monotonic_cumulative

A contract lists columns that are cumulative. The check fails when one of those columns decreases on a recorded frame.

```json
{"cumulative": ["Vaccinated_1st"]}
```

| Corpus id | Incident |
|---|---|
| SF-016 | covsirphy treated `Vaccinated_1st` as cumulative. The series jumped from about 9.7 million to 857 and back, because some rows were daily counts. Nothing raised. |

The report names the recorded call that held the decreasing column.
