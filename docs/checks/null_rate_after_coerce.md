# null_rate_after_coerce

Records the null fraction of `to_datetime`, `to_numeric` and `astype`, and fails when that fraction is more than 0.01 above the baseline.

| Corpus id | Incident |
|---|---|
| SF-001 | Corpus id only. A `to_datetime(errors="coerce")` turned values into nulls and a later drop removed the rows. The public corpus does not include this row. |
| SF-020 | USGS `dataretrieval`: incomplete timestamps became a `NaT` index with no warning, and the rows fell out of order. |
| SF-021 | Apache Superset: a mismatched `python_date_format` coerced an entire column to `NaT`. The column displayed as N/A and nothing raised. |

The report names the coercion call.
