# Cursor report, 21 November 2026

Branch `review/2026-11-21`. Nothing was merged, tagged, or published. No email was sent and nothing was posted outside the pull request for this branch.

Author name used in new text: Kishan Raj VG.

## Task 1. Review the v0.8 work

**What I did.** Looked for `AUTOLINEAGE_HANDOFF.md` in the repo, under `OneDrive\Documents\Claude`, and in the Cursor project notes. Read `git log v0.7.1..HEAD` and `git diff --stat v0.7.1...HEAD`. Read the hook, check, and rebind code. Ran the suite. Fixed one restart bug and added tests. Did not merge.

**What I ran.**

- VERIFIED: `git log v0.7.1..HEAD` shows the 0.8 work on current `main`: JOSS paper edits, constructor records, text vectorizers, child-process capture, the five checks plus `metric_change`, the check-command fixes, and the 0.8.1 release commit. Remote tag `v0.8.0` points at `6072bec`. Remote tag `v0.8.1` points at `d0e046c`.
- VERIFIED: first full suite on `main`, before the branch: `177 passed in 86.00s`.
- VERIFIED: full suite on this branch after the fixes: `181 passed in 80.33s (0:01:20)`.
- VERIFIED: `pyproject.toml` and `.github/workflows/ci.yml` define no linter. The project venv has no `ruff` module and no `flake8` module (`No module named ruff`, `No module named flake8`). There is no linter result to report.
- VERIFIED: with pandas and scikit-learn importable and PySpark not installed, `HookRegistry.install_all` returned `[('pandas-io', 10), ('pandas-transforms', 60), ('sklearn', 235)]`, total 305. README pandas 70 and scikit-learn 235 match that measurement. README PySpark 49 was not measured live.

**Handoff.** ASSUMED that no handoff file exists outside the places searched. VERIFIED that it is not in the repo.

**Risk list.**

- Reentrancy. Depth counters are per thread, and a non-main thread with no user frame is skipped. VERIFIED by reading `autolineage/hooks/__init__.py` and by the existing thread tests, which the suite ran. A call whose code object filename is `<string>` is treated as a library frame. ASSUMED from reading `_is_library_frame`. Not exercised this session.
- Return values. The pandas and scikit-learn hooks return the original result, and a raised exception leaves the depth counter usable. VERIFIED for `dropna` and `LogisticRegression.fit` by `tests/test_hook_exceptions.py`, included in the 181.
- Restart bug, fixed on this branch. A name imported while tracking was on (`f1_score`, `train_test_split`) kept the old hook object after `stop_tracking()` and `start_tracking()`. The new tracker then missed that call, and internal calls such as `LabelEncoder` inside the metric were recorded as if the user had made them. `localize_root_cause("f1_score")` then saw no metric. VERIFIED by a script on PyPI 0.8.1: after a restart, the records were `concat`, `filter`, `select`, `dropna`, `filter`, `drop`, `RandomForestClassifier.__init__`, `fit`, `predict`, and three `LabelEncoder` records, and the reported metric was `0.0000 -> 0.0000`. The same calls with the import repeated after `start_tracking()` did record `train_test_split` and `f1_score`. The branch rebinds a leftover hook. VERIFIED by `test_a_name_imported_during_tracking_is_rebound_on_restart`, included in the 181.
- Behavior without a new test, still true. `benchmarks/checks/` is a synthetic check suite. Its result file was not regenerated this session. Child-process capture and the check command have tests from the 0.8 work; those tests ran as part of the 181.
- Dependencies. VERIFIED from `pyproject.toml`: runtime dependencies are still `pandas` and `numpy`. `multiprocess` is a dev extra, added in 0.8.1. No new runtime dependency on this branch.
- README claims. VERIFIED by running it: the hero snippet on PyPI 0.8.1 raises `FileNotFoundError: [Errno 2] No such file or directory: 'data.csv'`. The repository has no `data.csv`. This branch points that snippet at `examples/pipeline.py` (Wisconsin breast cancer). VERIFIED on PyPI 0.8.1, whose library already supports that script: `F1 = 0.9693` and `<UnifiedTracker: 11 operations across pandas-transforms, sklearn>`. The published README is unchanged until a release.
- ASSUMED from reading the README, not re-run: the credit-card example lists 18 operations and the prose says "24 clean records." The dataset file was not run this session.
- The README still prints the 84.7 µs microbenchmark and `docs/benchmarks.md` still prints the synthetic check-suite result. I did not delete those. They conflict with the "no synthetic numbers" rule. Decision below.
- The notebook's saved output says 11 operations and no constructor record. VERIFIED live on PyPI 0.8.1: the same cells record 12 operations, including `RandomForestClassifier.__init__`. I did not rewrite the stored notebook outputs.
- Polars. VERIFIED by search: the only mention in code or docs is a 0.6 changelog line that real Polars support was planned for 0.8.0. There is no Polars hook.

## Task 2. Fresh-install test

**What I ran.** Created `C:\Users\kisha\AppData\Local\Temp\al_fresh_312` with `C:\Users\kisha\miniconda3\python.exe -m venv`, then `pip install "autolineage[sklearn]"` with no clone on `sys.path`.

- VERIFIED: Python `3.12.4 | packaged by Anaconda, Inc. | (main, Jun 18 2024, 15:03:56) [MSC v.1929 64 bit (AMD64)]`.
- VERIFIED: `autolineage.__version__` is `0.8.1`.
- VERIFIED: Python 3.11 is not installed. `py -3.11` prints `No suitable Python runtime found`. The 3.11 half of this task was not run.
- VERIFIED: README hero as published, in an empty directory: hooks install (`305 hooks installed across 3 frameworks (pandas-io, pandas-transforms, sklearn)`), then `FileNotFoundError` on `data.csv`. Exit code 1. The library and the README on PyPI 0.8.1 are the same text as the repo before this branch, so the failure is in the published release and in the repo. The branch fixes the repo copy only.
- VERIFIED: `examples/pipeline.py` with that same interpreter, from a directory that is not the clone: the output above (`F1 = 0.9693`, 11 operations, `wrote trace.html`).
- VERIFIED: Colab notebook cells, `%pip` skipped because the package was already installed. Without IPython, `to_jupyter` raises `RuntimeError: IPython is not installed; install autolineage[jupyter]`. The notebook's install cell asked only for `autolineage[sklearn]`. Colab already has IPython; a fresh venv does not. This branch changes that cell to `autolineage[sklearn,jupyter]`.
- VERIFIED: after `pip install ipython` in the fresh venv, the same cells finished. First pipeline: `rows after filter: 19,980   F1 = 0.8027` and `<UnifiedTracker: 12 operations across pandas-transforms, sklearn>`, including `train_test_split`, `RandomForestClassifier.__init__`, `fit`, `predict`, and `f1_score`. Second pair: `[clean] rows after filter: 19,980   F1 = 0.8027`, `[buggy] rows after filter: 1,000   F1 = 0.0000`, then `[critical] filter row change: -19,000 (baseline: -20, 94900% deviation)`, `[critical] f1_score dropped from 0.8027 to 0.0000 (-100.0%)`, and `The most likely cause of the f1_score drop (from 0.8027 to 0.0000) is 'filter' at step 5. Row change was -19,000 (baseline: -20).` Those figures come from the notebook's generated table. They are not a benchmark.

## Task 3. Prepare v0.8.0

**Not done, on purpose.** VERIFIED: `v0.8.0` is already a remote tag at `6072bec`, and `v0.8.1` is the current PyPI release (`pip index` was not required; the fresh install resolved `0.8.1`). VERIFIED from `pyproject.toml`: `authors` is already `Kishan Raj VG`. Polars eager support is not in the tree, so there is no real pipeline to confirm and no release PR. Version was not bumped. I will not tag or publish.

## Task 4. Onboarding and issue templates

**What I did.** Added `docs/ONBOARDING.md` and `.github/ISSUE_TEMPLATE/` with a bug report, a silent-failure report (pipeline, framework, what ran fine, what was wrong), and a feature request. No "used by" page.

The onboarding example is the breast-cancer script. VERIFIED figures in that doc, from the fresh 0.8.1 install: `F1 = 0.9693`, 11 operations, and for a second run with `mean radius < 10` the anomaly `[critical] filter row change: -522 (baseline: -5, 10340% deviation)`. F1 on that second run was `1.0000`, and `localize_root_cause("f1_score")` returned `None`.

## Task 5. Corpus selection rule

**What I did.** Wrote `benchmarks/real/SELECTION_RULE.md` and committed it on its own with a dated message. Did not edit `benchmarks/real/PROTOCOL.md`. Did not edit or rerun anything under `benchmarks/real/heldout_results/`. Did not score a new fault.

**Coverage.** VERIFIED by reading the committed files, not by a new scoring run:

- `benchmarks/real/heldout_results/evaluated_build/summary.json`: `n_cases` 27, `n_scored` 2, `mean_coverage` 0.29166666666666663.
- `benchmarks/real/heldout_results/summary.json` (the re-score): `n_cases` 27, `n_scored` 2, `mean_coverage` 0.29166666666666663.

ASSUMED that a fresh scoring run would still produce those figures. `run_heldout.py` is locked and I did not run it.

## Task 6. acryldata/mcp-server-datahub commit a376b3c

**What I ran.** `gh` against `acryldata/mcp-server-datahub`. No clone and no tooling.

- VERIFIED: `a376b3c` is `a376b3cd193b2dc95f4d0e8cf4f9cfac2370417f`, dated 2026-10-16, message `Merge pull request #238 from kishanraj41/fix-datajob-input-output`.
- VERIFIED: compare `a376b3cd193b2dc95f4d0e8cf4f9cfac2370417f...v0.8.0` returned `{"status":"ahead","ahead_by":33,"behind_by":0}`. The commit is an ancestor of release `v0.8.0`.
- VERIFIED: compare against `v0.7.1` returned `{"status":"behind","ahead_by":0,"behind_by":39}`. `v0.7.1` does not contain it.
- VERIFIED: `gh release list` shows `v0.8.0` as Latest, published 2026-10-21. No later release is in that list. So the released versions that contain the commit are: `v0.8.0` only.

## Open problems

- PyPI 0.8.1 still has the `data.csv` quickstart, the restart hole, and the notebook install cell that does not request IPython. This branch fixes the repo. A release is required before `pip install autolineage` picks them up.
- Polars was planned for 0.8.0 and did not ship in 0.8.0 or 0.8.1.
- Python 3.11 was not available, so the fresh install was 3.12 only.
- README credit-card block says 24 records and prints 18 lines. Not re-run.
- Saved notebook outputs predate constructor records.
- No project linter is configured.

## Decisions I need

1. Polars eager support. I did not start it. Say if you want it as the next version (0.8.2 or 0.9.0), and name the real pipeline it has to run on. I will not invent a benchmark number for it.
2. The 84.7 µs table and the synthetic check-suite pages are still in the README and docs. Say if they should come out. I left the frozen held-out files and `PROTOCOL.md` untouched.
3. Whether to release the fixes on this branch. I will not tag or publish unless you say so.
