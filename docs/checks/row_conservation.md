# row_conservation

Two rules, both with a tolerance of 0.01.

**Steps that change a frame.** Compares `rows_after` with `rows_before` at each recorded step against the matching step in a saved baseline. A step fails when its row-change rate differs from the baseline rate by more than 0.01. This is the rule for a merge that multiplies rows and for a filter or slice that drops them.

**Loads.** A load (`read_csv`, `read_parquet` and the other readers) has no rows before it, so it is compared by row count. A load fails when it returns more than 1% fewer rows than the same load in the baseline. A load that returns more rows passes, since data that grows between runs is normal. This is the rule for a file that arrives truncated.

Steps are matched by aligning the two operation sequences, so a step added to the script does not shift the comparison for the steps after it. A step with no partner in the baseline is not compared.

| Corpus id | Incident |
|---|---|
| SF-002 | PHE COVID lab files loaded into `.xls` templates. Rows past the 65,536-row cap were dropped and 15,841 cases were missing. |
| SF-018 | A priority merge dropped state-level death counts that existed only in a lower-priority source. |
| SF-022 | A pandas merge of `int64` and `uint64` keys upcast to `float64` and produced duplicate rows. `validate="1:1"` did not raise. |

The report names the file and line of the step whose rate moved.

## What it does not see

- Rows lost before the data reaches pandas. SF-002 lost its rows inside a spreadsheet template; the check sees that loss only as a smaller load in the next run.
- A load that shrinks by 1% or less.
- A change in which rows are kept when the count stays the same.
