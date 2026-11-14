# row_conservation

Compares `rows_after` with `rows_before` at each recorded step against the same step in a saved baseline. A step fails when its row-change rate differs from the baseline by more than 0.01.

This is the check for a merge that multiplies rows and for a load or a slice that drops them.

| Corpus id | Incident |
|---|---|
| SF-002 | PHE COVID lab files loaded into `.xls` templates. Rows past the 65,536-row cap were dropped and 15,841 cases were missing. |
| SF-018 | A priority merge dropped state-level death counts that existed only in a lower-priority source. |
| SF-022 | A pandas merge of `int64` and `uint64` keys upcast to `float64` and produced duplicate rows. `validate="1:1"` did not raise. |

The report names the file and line of the step whose rate moved.
