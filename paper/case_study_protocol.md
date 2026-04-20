# AutoLineage Case Study Protocol
## Debugging a Planted Data Quality Bug

### Purpose
Measure whether AutoLineage helps practitioners find data-quality bugs faster
than manual debugging. This case study goes in the paper as Section 5.5.

### Participants
| ID | Name | Role | Condition |
|----|------|------|-----------|
| P1 | Goutham | ML Engineer | **Manual** (USE_AUTOLINEAGE = False) |
| P2 | Kishan | ML Engineer | **AutoLineage** (USE_AUTOLINEAGE = True) |

We give the harder condition to the person who has NOT seen the pipeline before
(Goutham). Kishan has written the code but will still time his own debugging
session with AutoLineage as a self-reported upper bound.

### The Bug
In `case_study_pipeline.py`:
```python
df = df[df['Amount'] < 0.01]  # WRONG — was meant to be > 0.01
```
This removes 99.99% of transactions (keeps only pennies), leaving almost no
fraud cases in the training set. The model reports F1 near zero.

---

## Protocol

### 1. Before the session (Kishan, ~10 min)
- Verify `case_study_pipeline.py` runs and produces F1 ≈ 0.0
- Open a screen recording app (OBS, Zoom cloud recording, Windows Game Bar)
- Have two terminal windows ready:
  - One with `USE_AUTOLINEAGE = True`
  - One with `USE_AUTOLINEAGE = False`

### 2. Running the session (30 min total)

**Part A — P1 (Goutham, manual condition): 15 minutes**
1. Share your screen to Goutham via Zoom/Meet
2. Read this exactly:
   > "I'm going to show you a fraud-detection pipeline producing F1 = 0.00.
   > Something is wrong with the data. Find the root cause. Think out loud
   > as you work. You can add print statements, run subsets of the code,
   > anything except changing the filter line. You have 15 minutes max."
3. Let Goutham drive. Start a timer.
4. Record each step he takes (see template below).
5. When he identifies the bug (or 15 min expires), stop the timer.
6. Ask post-study questions.

**Part B — P2 (Kishan, AutoLineage condition): 5 minutes**
1. Switch to the `USE_AUTOLINEAGE = True` file.
2. Run the pipeline. Look at the output.
3. Time yourself from "output appeared" to "identified bug".
4. Fill in your own template.

### 3. What to record

For each participant:

| Step # | Time (mm:ss) | Action | Finding |
|--------|--------------|--------|---------|
| 1 | | | |
| 2 | | | |
| 3 | | | |

Example entries:
- "00:45 | Ran df.shape after read_csv | 284807 rows, OK"
- "02:30 | Read AutoLineage trace output | Filter step shows -284780 rows"

---

## Data Collection Template

### Participant P1: Goutham (Manual)
**Start time:** _______
**Bug identified at step #:** _______
**Time to detection:** _______ min
**Detection method:** (e.g., "print(df.shape) between each step")

| # | Time | Action | Finding |
|---|------|--------|---------|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |
| 6 | | | |
| 7 | | | |
| 8 | | | |

**Post-study questions:**
1. Confidence in diagnosis (1–5): ___
2. Would a lineage trace have helped? (1–5): ___
3. How often do you see bugs like this in practice? ___
4. Would you use an auto-lineage tool day-to-day? Why or why not?

---

### Participant P2: Kishan (AutoLineage)
**Start time:** _______
**Bug identified at step #:** _______
**Time to detection:** _______ min
**Detection method:** (e.g., "analyzer.localize_root_cause() pointed to the filter")

| # | Time | Action | Finding |
|---|------|--------|---------|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |

**Post-study questions:** (same as above)

---

## Expected Results

| Metric | Manual (P1) | AutoLineage (P2) |
|--------|-------------|-------------------|
| Time to detection | 5–12 min | 1–3 min |
| Steps to detection | 4–8 | 1–2 |
| Detection method | `df.shape` checks at each stage | Trace output + `localize_root_cause()` |

AutoLineage should be faster because the trace immediately shows the row
count drop from ~284K to ~30 at the filter step, and `localize_root_cause()`
programmatically identifies the same operation with impact score > 0.99.

### How we write this up in the paper

> To evaluate practical utility, we conducted a small-scale case study
> with two ML practitioners debugging a planted data-quality bug—an
> overly aggressive filter removing 99.99% of records. Participant P1
> debugged manually, requiring X steps and Y minutes, adding
> `print(df.shape)` between each operation. Participant P2, with
> AutoLineage enabled, identified the bug in Z minutes by reading the
> trace output, where the row count drop from 284K to ~30 at the
> filter operation was immediately visible. The `localize_root_cause()`
> method programmatically flagged the same operation with an impact
> score of 0.99. With N=2, this study is illustrative rather than
> statistically powered; it demonstrates the mechanism by which
> lineage tracing accelerates root-cause analysis.

This is honest about N=2 while still providing useful evidence.

---

## After the Session

1. Send me (Claude) the completed templates above.
2. Include any screen recordings as evidence (optional, for backup).
3. I'll write Section 5.5 of the paper using your data.
