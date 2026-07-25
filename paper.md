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
  - name: Kishan Raj Vandhavasi Goutham Kumar
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
instruments pandas, scikit-learn, and PySpark at load time (288 framework methods),
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
microseconds per operation (95% CI [78, 91]) on a 37-operation pandas/scikit-learn
benchmark, low enough to leave enabled in notebooks and CI (reproduction scripts in
`benchmarks/`).

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
blend of row-count deviation (0.6), column-count change (0.3), and novelty (0.1). The
weighting is a deliberate heuristic rather than a learned model: bugs in this class
surface first and most violently as row-count anomalies, so the proximate cause outranks
the downstream operations that merely inherit its damage.

# Evaluation

A controlled study in `benchmarks/planted_bugs/` injects five bug categories (filter
corruption, join fan-out, encoding blow-up, target leakage, and type coercion) into a
fixed pipeline, changing one line each. `AutoLineage` detected the structural change in
all five cases and localized the exact operation in three (filter, join, type); the
remaining two were flagged correctly but attributed to the adjacent recorded operation.
The localization used the library's default weights, which were not tuned on these five
pipelines, so the result reflects out-of-the-box behaviour on previously unseen pipelines.
The scripts fix all random seeds and reproduce every number reported here. A companion
preprint [@vg2026autolineage] describes the hooking methodology and the overhead and
scaling studies in more detail.

# Limitations

`AutoLineage` detects structural drift (row counts, column counts, and end metrics), not
shape-preserving semantic bugs such as a unit error that rescales a column while leaving
its shape intact. It assumes a single dominant root cause, and its default localization
weights and thresholds are heuristics tuned on a small set of pipelines rather than
learned. Coverage is pandas, scikit-learn, and PySpark, single-machine and in-process;
PyTorch, TensorFlow, Polars, and distributed execution are out of scope.

# Acknowledgements

I thank the maintainers of pandas [@pandas] and scikit-learn [@sklearn], on which this
work builds.

# References
