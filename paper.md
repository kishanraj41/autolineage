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
date: 17 October 2026
bibliography: paper.bib
---

# Summary

`AutoLineage` is a Python library that records what a machine-learning pipeline does
to its data, one operation at a time, and points to the operation most likely to be
responsible when a model metric gets worse. A single `import autolineage.auto`
statement instruments pandas, scikit-learn, and PySpark at load time, with no
decorators and no manual logging. Each transformation is recorded with its input and
output shapes, the columns it touched, its timing, and the line of user code that
issued it. The records form a directed acyclic graph that can be queried as JSON or
exported to Graphviz, Mermaid, an interactive HTML view, or OpenTelemetry spans. An
analyzer compares a run with a saved baseline fingerprint, flags anomalies, and ranks
the operations most likely to have changed a metric.

# Statement of need

Machine-learning pipelines fail silently. A mis-specified filter, a join that fans out,
or a label left in the feature matrix raises no exception: the pipeline finishes and
writes its metrics file. The most-watched metric can hide the failure. In an imbalanced
fraud task, a filter that removes almost all positive examples leaves accuracy at 0.998
while F1 falls to zero. Sambasivan et al. [@Sambasivan2021] called this family of
failures "data cascades", and 92% of the practitioners they interviewed had seen one.

When a metric moves between two runs, the practical question is which line changed the
data. `AutoLineage` answers it after the fact, without re-instrumenting the pipeline.
It is for data scientists, ML engineers, and researchers studying pipeline failures,
on single-machine, in-process Python pipelines.

# State of the field

Experiment trackers such as MLflow [@mlflow] record run-level parameters and artifacts,
not the operations between them. Data-version tools such as DVC [@dvc] version files
and see nothing when only the code changed. Drift monitors such as Evidently
[@evidently] compare distributions against a configured reference. OpenLineage
[@openlineage] records lineage per job, not per operation.

The closest research tools work inside the script. mlinspect [@grafberger2021mlinspect;
@grafberger2022distribution] also patches pandas and scikit-learn to build an operator
DAG and runs user-declared inspections and checks over one execution, for example
whether an operation changes the distribution of a sensitive column. Vamsa
[@namaki2020vamsa] statically infers which columns of a dataset feed a trained model.
noWorkflow [@murta2014noworkflow] captures general provenance of Python scripts at the
level of function calls and variables.

`AutoLineage` asks a different question: across two runs, which operation explains a
metric change? It records without user code changes or wrapping the run in an
inspector call. That cross-run comparison and scoring needs a fingerprint format and a
ranking layer that neither mlinspect's single-run inspection model nor job-level
lineage provides, so we built a separate library. Its hook layer emits standard
OpenTelemetry spans so it can feed existing lineage and observability backends.

# Software design

The central decision is how to observe a pipeline. Decorators and wrapper classes
require editing every pipeline, which excludes the exploratory notebooks and inherited
code where silent bugs are common. A DataFrame subclass breaks as soon as a library
returns a plain pandas object. `AutoLineage` instead monkey-patches framework methods at
import time. The trade-off is version sensitivity and single-process scope in exchange
for zero-configuration capture. Hooked methods call other hooked methods internally, so
a depth counter maintained in a `finally` block records a node only for the outermost
call. This reduces a 24-step pipeline from 152 raw records to the 24 operations the
user wrote.

Granularity is one node per user-visible framework call: the finest level at which a
structural bug becomes visible and the coarsest at which a person can still read the
trace. Each framework is a plugin, a `BaseHookProvider` subclass of roughly 200 lines,
which isolates the version-sensitive surface. Because pandas copies `DataFrame.attrs`
onto derived frames, every derived frame is given its own lineage ID; otherwise the
graph collapses into self-loops.

Localization aligns the baseline and current operation sequences with
`difflib.SequenceMatcher`, so an unmatched operation that removed rows is reported as
inserted. Operations are scored by a fixed weighted blend: row-change-rate deviation
(0.6), the origin of a column-set change (0.4), column-count change (0.3), and novelty
(0.1). Column-set changes are credited only where they originate, because a bare
column-count change is inherited by every later operation. The weights are a
heuristic, not a learned model.

Per-call overhead depends on the machine and session. For a small `dropna`, one laptop
measured 84.7 µs per hooked call in one interleaved benchmark and about 206 µs in a
later session in which the uninstrumented baseline was also twice as slow
(`paper/microbenchmark_v2.py`).

# Research impact statement

`AutoLineage` is at an early stage of research use; this section states only what
exists today.

It is the measurement layer for the author's research on localizing faults in ML
pipelines, and a companion preprint [@vg2026autolineage] describes the hooking method.
`benchmarks/real/` is a reproducible reference analysis. Public GitHub scripts that
already train scikit-learn models receive single faults by AST mutation, under a
protocol frozen before scoring (`PROTOCOL.md`). On the held-out half, 2 of 27 mutations
produced a scorable metric change; 20 had no site in the script, 1 changed no metric,
and 4 crashed. AutoLineage flagged both scorable faults and ranked the mutated line
first for 1 of the 2. Neither unmutated rerun raised a warning or critical anomaly.
Mean coverage of pipeline lines was 0.29. These numbers are too small to support
accuracy claims; the corpus and scorer are published so that larger studies can reuse
them.

The RudriQ project integrates `AutoLineage` through its post-record and `assign_id`
callbacks, and several changes in versions 0.6–0.7 were made for that integration.
External adoption and citations are not yet established.

# AI usage disclosure

Generative AI was used in developing this software and paper. Anthropic's Claude,
mainly through Claude Code, was used to review diffs, write and extend tests, draft
docstrings, documentation and parts of this paper, and propose refactors. Commits with
substantial AI contribution carry a `Co-Authored-By: Claude` trailer. The author
decided the problem framing, the hooking architecture, the localization scoring, and
the benchmark protocol and selection rules; wrote or reviewed every change before
merging; ran the test suite and benchmarks; and checked reported numbers against the
per-case result files.

# Limitations

`AutoLineage` detects structural drift in row counts, columns, and end metrics, not
shape-preserving semantic bugs such as a unit error that rescales a column. It assumes
a single dominant root cause. Coverage is pandas, scikit-learn, and PySpark in a single
process; PyTorch, TensorFlow, Polars, and distributed execution are out of scope.

# Acknowledgements

I thank the maintainers of pandas [@pandas] and scikit-learn [@sklearn], on which this
work builds. This work received no external funding.

# References
