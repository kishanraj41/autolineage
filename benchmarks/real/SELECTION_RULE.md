# Selection rule for any further real-pipeline scoring

Written 21 November 2026, before any further fault scoring. The study already scored stays under `benchmarks/real/PROTOCOL.md`, which was frozen on 10 October 2026. This file does not change that protocol, those scripts, or those result files. A later scoring run uses this file. A case that this file does not clearly accept is not scored.

## What counts as a real pipeline

A real pipeline is someone else's published script that trains or evaluates a model with pandas and scikit-learn, and that reads a dataset the script or its repository identifies. The script and the dataset are used as published. A script written for this repository, a tutorial rewritten for the study, or a notebook reduced to a few cells is not a real pipeline.

PySpark and Polars scripts are out of this rule until a separate rule is written for them. This rule does not score them.

## What counts as a scoreable fault

A scoreable fault is one planted change, applied by `benchmarks/real/mutate.py` to one recorded span, that the unmutated script did not already have. The planted line is the ground truth. The fault is scoreable only when the mutated script finishes and the recorded metric changes. A mutation that has no site in the script, crashes, or leaves the recorded metric unchanged is counted in the report and is not a scored detection.

Bugs taken from commit history are not scoreable faults under this rule.

## Inclusion

A candidate comes from a GitHub code search that is saved before any file from that search is run. The query, the date, and the saved order go in the run notes. Hits are taken in the saved order. The first hits that pass the exclusion list fill the slots. The pool is not extended after a file from it has been run.

## Exclusion

The first matching reason wins. Record the reason.

1. The repository licence is not MIT, BSD-2-Clause, BSD-3-Clause, Apache-2.0, ISC, or MPL-2.0.
2. The path is under `test/`, `tests/`, or `testing/`, or the file name starts with `test_` or ends with `_test.py`.
3. The file does not mention both pandas and scikit-learn.
4. The dataset cannot be named from the script: a `read_csv` of a file in the same repository, a `read_csv` of `archive.ics.uci.edu`, or a scikit-learn or OpenML loader. A Kaggle dataset counts only when the script or the repository README states a dataset licence of CC0, CC BY, or public domain. The code's own licence is not a dataset licence.
5. The file cannot be fetched.
6. After the adapter below, the unmutated script does not exit 0 within 300 seconds.

The adapter may delete `google.colab`, `files.upload`, and `drive.mount` lines, and may point a relative `read_csv` at a cached copy of a file already in that repository. Any other edit excludes the hit. The adapter is written down. It is not a mutation.

A repository with no OSI licence can be used to debug. Its source is not copied into this repository and its numbers are not published. It cannot enter the held-out split.

## Who decides

Kishan Raj VG decides whether a hit is in or out, by applying this file in order. A hit is not included because it looks like a good demo, and it is not dropped because a result was inconvenient.

## Ambiguous cases

If two reasons could apply, the earliest reason in the exclusion list is the one recorded. If the dataset licence, the adapter, or the question of whether the script is someone else's pipeline is still unclear after reading the script and the repository README, the hit is excluded and the note says `ambiguous`. An ambiguous hit is not scored and is not revisited in the same run. Changing this file to admit it is a new rule, and the run that uses the new rule starts after the change is committed.
