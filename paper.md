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
pipeline does to its data, operation by operation, and then localizes the operation
responsible when a metric regresses. A single `import autolineage.auto` statement
monkey-patches pandas, scikit-learn, and PySpark at load time (288 framework methods
across the three, 239 when PySpark is absent) and captures every transformation with
its shape before and after, the columns it touched, and timing metadata. No decorators,
no manual logging, and no changes to the pipeline code are required. The captured
execution is an in-memory directed acyclic graph that can be queried as JSON or exported
to Graphviz, Mermaid, or a self-contained HTML view. On top of the graph, an analyzer
compares a run against a saved baseline fingerprint, flags anomalies, and reports the
single operation most likely to have caused a metric to change.

# Statement of need

Machine-learning pipelines fail silently. A single mis-specified filter, a join that
fans out, an encoding applied to the wrong column, or a label accidentally left in the
feature matrix will not raise an exception; the pipeline runs to completion and writes
its metrics file. The most-watched metric often hides the failure: in an imbalanced
fraud task, a filter that removes almost all positive examples leaves accuracy at 0.998
while F1 collapses from 0.984 to 0.000. Sambasivan et al. [@Sambasivan2021] documented
this family of "data cascades" and reported that 92% of the practitioners they
interviewed had encountered them.

Existing tooling watches the wrong layer. Experiment trackers such as MLflow [@mlflow]
record run-level inputs and outputs, not the operations in between. Data-version tools
such as DVC [@dvc] version files, so they see nothing when the input file is unchanged
and only the code changed. Drift monitors such as Evidently [@evidently] compare against
a reference distribution that many teams never configure. Lineage standards such as
OpenLineage [@openlineage] operate at the job level rather than the individual pandas or
scikit-learn call. The result is a blind spot between "data loaded" and "metric
computed" in which these bugs live.

`AutoLineage` fills that blind spot for in-process, single-machine Python pipelines. It
is aimed at data scientists and ML engineers who need to know, after the fact and
without re-instrumenting anything, which line changed the data and therefore the model.
The zero-configuration capture makes it usable in exploratory notebooks, and the
baseline-comparison analyzer makes it usable in continuous integration to guard against
silent regressions.

# Key features

- Import-time instrumentation of pandas, scikit-learn, and PySpark with no code changes.
- A reentrancy guard (a depth counter incremented on entry to each hooked method and
  decremented in a `finally` block) that records only user-level operations. Without it,
  a 24-step pipeline produced 152 lineage records; with it, exactly 24.
- Anomaly detection and root-cause localization against a saved baseline fingerprint,
  scoring each operation by row-count deviation (weight 0.6), column-count change (0.3),
  and novelty (0.1).
- Export to JSON, Graphviz DOT, Mermaid, and an interactive HTML graph.
- Low overhead: 84.7 microseconds per operation (95% CI [78, 91]) on pandas and
  scikit-learn, below the measurement noise floor on PySpark.

# Evaluation

Beyond the original single-bug demonstration, a controlled study injects five distinct
bug categories (filter, join fan-out, encoding blow-up, target leakage, and type
coercion) into a fixed pipeline, changing one line each. `AutoLineage` detected the
structural change in all five cases and localized the exact operation in three
(filter, join, type), with the remaining two flagged correctly but attributed to the
adjacent recorded operation. The scripts reproduce every number. As stated in the
software's own documentation, shape-preserving semantic bugs that alter no row or column
count remain out of scope.

# Acknowledgements

We thank the maintainers of pandas [@pandas] and scikit-learn [@sklearn], on which this
work builds.

# References
