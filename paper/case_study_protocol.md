# AutoLineage case study

The author is one person: Kishan Raj Goutham Kumar (kishanraj41). An earlier
draft of this file split that name into two participants, "Goutham" and
"Kishan", and assigned them the manual and AutoLineage conditions. Those
are not two people. There is no second participant, and there is no N=2
result.

No session was run. This case study is not in the paper. A timing of the
author debugging his own pipeline would be a self-study, and it is not
reported.

`case_study_pipeline.py` still contains the planted filter

```python
df = df[df['Amount'] < 0.01]  # WRONG — was meant to be > 0.01
```

which keeps only amounts under one cent. `USE_AUTOLINEAGE` switches the
library on or off for a demo run. It does not select a participant.
