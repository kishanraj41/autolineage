---
title: 'AutoLineage: Operation-level data lineage and root-cause localization for Python ML pipelines'
tags:
  - Python
  - machine learning
  - data lineage
  - MLOps
  - reproducibility
  - data engineering
authors:
  - name: Kishan Raj VG
    orcid: 0009-0007-6488-5855
    affiliation: 1
affiliations:
  - name: University of the Cumberlands, USA
    index: 1
date: 11 July 2026
bibliography: paper.bib
---

# Summary

`AutoLineage` is a Python library that automatically records what a machine-learning
pipeline does to its data, operation by operation, and localizes the operation
responsible when a model metric regresses. A single `import autolineage.auto` statement
instruments pandas, scikit-learn, and PySpark at load time (289 framework methods),
capturing every transformation with its input and output shapes, the columns it touched,
and timing metadata, with no decorators, no manual logging, and no changes to the
pipeline code. The captured execution forms an in-memory directed acyclic graph that can
be queried as JSON or exported to Graphviz, Mermaid, or a self-contained interactive HTML
view. On top of the graph, an analyzer compares a run against a saved baseline
fingerprint, flags anomalies, and reports the single operation most likely to have caused
a metric to change.

# Statement of need

Machine-learning pipelines fail silently. A mis-specified filter, a join that fans out,
an encoding applied to the wrong column, or a label accidentally left in the feature
matrix raises no exception; the pipeline runs to completion and writes its metrics file.
The most-watched metric often hides the failure: in an imbalanced fraud task, a filter
that removes almost all positive examples leaves accuracy at 0.998 while F1 collapses
from 0.984 to 0.000. Sambasivan et al. [@Sambasivan2021] documented this family of
"data cascades," which 92% of the practitioners they interviewed had encountered.

Existing tooling watches other layers. Experiment trackers such as MLflow [@mlflow]
record run-level parameters and artifacts, not the operations in between. Data-version
tools such as DVC [@dvc] version files, and therefore see nothing when the input file is
unchanged and only the code changed. Drift monitors such as Evidently [@evidently]
compare data distributions against a configured reference rather than tracing pipeline
structure. Lineage standards such as OpenLineage [@openlineage] operate at the job level
rather than the individual pandas or scikit-learn call. The result is a blind spot
between "data loaded" and "metric computed" in which these bugs live. `AutoLineage`
fills that blind spot for in-process, single-machine Python pipelines: data scientists
and ML engineers can determine, after the fact and without re-instrumenting anything,
which line changed the data and therefore the model.

# Design and key decisions

The central decision is how to observe a pipeline. Decorators and wrapper classes require
the user to modify every pipeline they want to watch, which excludes the exploratory
notebooks and inherited pipelines where silent bugs are most common. A custom DataFrame
subclass intercepts operations but breaks the moment a library returns a plain pandas
object. `AutoLineage` instead monkey-patches the framework methods at import time, so
unmodified user code is observed transparently. The trade-off is stated plainly in the
documentation: the approach is version-sensitive and single-process, in exchange for
zero-configuration capture of code the user never has to touch. Measured overhead is 84.7
microseconds per hooked call (95% CI [78, 91]) in an interleaved microbenchmark of a
small `dropna`, low enough to leave enabled in notebooks and CI (reproduction script
`paper/microbenchmark_v2.py`).

Patching at this level creates a reentrancy problem: hooked methods invoke other hooked
methods internally, so a single `fit()` triggers several times as many hooked calls as
user-visible operations. A depth counter, incremented on entry to each hooked method and
decremented in a `finally` block, records a node only at depth zero. It reduces a 24-step
pipeline from 152 raw records to exactly the 24 operations the user wrote, and the
`finally` placement keeps the counter correct even when an operation raises.

The second decision is granularity. File-level lineage (DVC) and job-level lineage
(OpenLineage) sit above the layer where these bugs live: a filter that drops the wrong
rows changes neither the input file nor the job graph. `AutoLineage` records one node per
user-visible framework call, the finest granularity at which a silent structural bug
becomes visible and the coarsest at which a human can still read the trace.

Each supported framework is a plugin: a `BaseHookProvider` subclass in its own file
implementing `install()` and `uninstall()`, registered in a central registry. Adding a
library is roughly 200 lines and touches none of the core, isolating the version-sensitive
surface per framework.

Finally, root-cause localization scores each operation against the baseline by a weighted
blend of row-count deviation (0.6), column-set change at its origin (0.4), column-count
change (0.3), and novelty (0.1). The column-set term compares the names of the columns
each operation produced, created, and removed, and credits a change only to the
operation where it originated: a column the baseline never saw, a column the baseline
deliberately removed that the current run never removes (the target-leakage signature),
or a column the baseline created that the current run never creates. The weighting is a
deliberate heuristic rather than a learned model: bugs in this class surface first and
most violently as row-count anomalies, and column-set changes are attributable to one
operation where a bare column-count change is inherited by every operation downstream.

# Evaluation

Published detection and localization numbers come only from the held-out half of the
corpus in `benchmarks/real/`. The protocol was frozen on 10 October 2026, before any
script in that corpus was scored, and is the file `benchmarks/real/PROTOCOL.md`.
The per-case records of the one held-out run are in `benchmarks/real/heldout_results/`.

A case is a public Python script that already trains a scikit-learn model on pandas
data, plus one fault inserted by an AST mutation. The script and the dataset are the
ones the repository published. The fault is planted, and the planted line is the
ground truth. Bugs mined from commit history are a later study and are not in this
submission.

For each planted fault that changes a recorded metric, the paper reports detection
(any warning or critical anomaly), top-1 and top-3 localization of the mutated line,
false positives on an unmutated rerun, the share of pipeline calls that produced a
record, and wall-clock overhead. The same cases are scored against three baselines:
the largest row drop, the last step whose rows changed, and a seeded random choice
among the script's pipeline lines. Faults with no site in the script, faults that do
not change a metric, and runs that crash are counted beside the rate and are not
inside it.

The candidate pools are the GitHub code searches named in the protocol. The first
pool did not yield enough scripts that finish. A second search, and then a third,
were added in that file before each search was scored. The development set has five
slots, and the library was allowed to change against those slots. All three searches
are exhausted. Four development scripts and three held-out scripts finished an
unmutated run; the rest of the planned slots did not qualify, and that shortfall is
recorded in the protocol. The held-out scripts were mutated once, after development
stopped. That run was not used to change the library.

Of 27 mutations, 20 had no site in the script, 1 left every recorded metric
unchanged, and 4 crashed. The rate is the other 2 faults, both planted in
`nazaninzareirad/SVM-paper` `visuals2.py`. `Devanik21/Harmonic-Resonance-Forest`
`hrf_conference.py` crashed on every applicable mutation. `duckyies/Fuzzy-knn`
`fknn.py` had no applicable mutation.

AutoLineage flagged an anomaly on both scored faults. The mutated line was the
first ranked cause for 1 of the 2, so top-1 and top-3 are both 1/2. On that fault
the largest-row-drop baseline and the last-changed-step baseline named the same
line. On the other fault the three ranked lines were other steps in the script,
and both of those baselines missed the mutated line as well. A seeded random
choice among pipeline lines named neither. Neither unmutated rerun of a scored
fault raised a warning or a critical anomaly. Mean coverage of pipeline-call
lines on the two scored runs was 0.29 (0.33 and 0.25). Mean framework-call
coverage on the same runs was 0.45 (0.55 and 0.36). Framework-call coverage
leaves subscript assignments out, and it keeps `fit`, `predict`,
`predict_proba`, `score`, and `astype` only when the receiver comes from
pandas or scikit-learn.

Wall-clock overhead on the two scored runs was 3.5 seconds and −8.5 seconds.
The mean is −2.5 seconds. Overhead is hooks-on wall time minus hooks-off wall
time, and scoring set `MPLBACKEND=Agg`. The operations AutoLineage recorded
on those runs took 1.5 and 2.6 seconds.

With the OpenML files already cached, wall time on this one script is not a
single number. Four alternating runs in one session took 19.2, 19.1, 19.1,
and 19.0 seconds (hooks off, on, off, on). Three alternating pairs in a later
session took 39.6 and 32.3, 37.2 and 31.0, and 34.6 and 30.6 seconds. Three
more pairs after that took 57.3 and 47.9, 55.0 and 49.4, and 53.9 and 55.1
seconds. Each pair is hooks off, then hooks on. These sessions sit beside the
per-call microbenchmark above, 84.7 microseconds for one small `dropna`.

The synthetic script previously used as a benchmark is a regression test under
`tests/regression/planted_bugs/`. It is not a result. A companion preprint
[@vg2026autolineage] describes the hooking methodology and the scaling studies in
more detail.

# Limitations

`AutoLineage` detects structural drift (row counts, column counts, and end metrics), not
shape-preserving semantic bugs such as a unit error that rescales a column while leaving
its shape intact. It assumes a single dominant root cause, and its default localization
weights and thresholds are heuristics. They may be adjusted on the development split.
They are not adjusted on the held-out split. Coverage is pandas, scikit-learn, and PySpark, single-machine and in-process;
PyTorch, TensorFlow, Polars, and distributed execution are out of scope.

# Acknowledgements

I thank the maintainers of pandas [@pandas] and scikit-learn [@sklearn], on which this
work builds.

# References
