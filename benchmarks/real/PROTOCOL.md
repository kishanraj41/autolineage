"""The real-pipeline benchmark.

Frozen on 10 October 2026, before any script in this corpus was scored.
The selection rule is this file. Slots are filled from it. They are not
reordered after a localization result.

## What "real" means

The code and the dataset are someone else's pipeline, used as published.
The fault is planted by an AST mutation. The planted line is the ground
truth. The paper says that plainly. Bugs mined from commit history are a
later study and are not part of this submission.

## Selection

Candidate pool: the first 100 hits of one GitHub code search, two pages of
50, retrieved once on 10 October 2026. The saved order is
`search_2026-10-10.json`. The pool is not extended after any file has been
run.

Query, as sent to `GET /search/code`:

    accuracy_score train_test_split read_csv extension:py

Order: the order the API returns. Pages are consumed in order.

A hit is skipped, and the skip is appended to `skipped.jsonl`, when any of
these is true. The first matching reason wins.

1. `no_osi_license`. The repository licence is not one of MIT, BSD-2-Clause,
   BSD-3-Clause, Apache-2.0, ISC, MPL-2.0.
2. `test_path`. The path is under `test/`, `tests/`, or `testing/`, or the
   file name starts with `test_` or ends with `_test.py`.
3. `missing_pandas_or_sklearn`. The file does not mention both pandas and
   sklearn.
4. `dataset_not_identified`. The script has no dataset this protocol can
   name: a `read_csv` of a file that is in the same repository, a
   `read_csv` of `archive.ics.uci.edu`, or a scikit-learn / OpenML loader
   (`fetch_openml`, `sklearn.datasets`, `load_iris`, `load_breast_cancer`,
   `load_diabetes`, `load_wine`, `load_digits`, `fetch_california_housing`,
   `fetch_covtype`, `fetch_20newsgroups`). A Kaggle dataset counts only
   when the script or the repository README states a dataset licence
   (CC0, CC BY, or public domain). The code's own OSI licence is not a
   dataset licence.
5. `file_unavailable`. The GitHub API does not return the file.
6. `does_not_run`. After the adapter below, the unmutated script does not
   exit 0 within 300 seconds.

The adapter may only delete `google.colab` / `files.upload` /
`drive.mount` lines and point a relative `read_csv` at the cached copy of
a file that is already in the repository. Any other edit is
`adapter_would_change_logic` and the hit is skipped. The adapter is
recorded in the manifest. It is not a mutation.

The first four hits that survive are dev slots 2 to 5. The next ten are
the held-out slots. Dev slot 1 is reserved and is not taken from this
search.

## Dev slot 1

`https://github.com/malick08012/End-to-End-ML-Pipeline-with-Scikit-learn-Pipeline-API-`
at `b35f523d18b06121746c85b588fc035d9f92eb30`. That repository has no OSI
licence. Its source is not copied into this repository. A clone may live
in the gitignored cache so the library can be debugged against it. Its
numbers are not published. It cannot move into the held-out split.

## Splits

Dev slots may be run as often as needed, and the library may change
because of what they show. Held-out slots are executed by
`run_heldout.py`, once, after that stops. That script is locked. It
refuses to run. Whatever that one run produces is the result in the paper,
including a weak one.

## Faults

Applied by `mutate.py`, one at a time, each a single span with a recorded
line. Other line numbers are not shifted.

- `insert_filter`. Append `.iloc[::2]` to the first `read_csv` call.
- `change_filter_threshold`. Multiply the first numeric threshold inside a
  filter subscript by ten (a zero becomes one).
- `change_join`. Swap `how` between left and inner (right and outer), or
  drop the last of several `on` keys, or add `how="inner"`.
- `drop_column`. Drop the last name in the first column list of length at
  least two.
- `leakage`. Fit the scaler on the full feature frame instead of the
  training split, or stop dropping the target column.
- `change_encoding`. Flip `drop_first` or `handle_unknown`, or add one of
  those arguments.
- `remove_dedup`. Replace `drop_duplicates(...)` with `copy()` on the same
  line, so the deleted step still has a line to name.
- `change_sampling`. Halve `sample(frac=)` or `sample(n=)`, or move
  `test_size` from below 0.5 to 0.5 (and the other way).
- `coerce_dtype`. Flip the argument of the first `astype`.

No pattern means not applicable. A run that finishes but moves no recorded
metric by more than one part in a million is `no_metric_change`. A crash
or a timeout is `crash`. Those three are counted. They are not in the
detection denominator. The scoring subprocess budget is 10 minutes. The
five-minute rule above is only the unmutated qualification. A timeout
kills the process tree; the first development run hung because a killed
pool left workers holding the pipes, and that hang produced no score.

## Measures

On scored cases only:

- Detection. Any warning or critical anomaly.
- Top-1. The mutated line is the source line of the first ranked cause.
- Top-3. The mutated line is among the first three ranked source lines.
- False positive. The same script with no fault, and the first
  `random_state` increased by one (or the identical script, if it has no
  `random_state`), produces a warning or critical anomaly.
- Coverage. The share of pipeline-call lines that appear as a record's
  source line. A pipeline call is a call whose leftmost name was imported
  from pandas or sklearn, or whose attribute is in `PIPELINE_ATTRS` in
  `score.py`, or an assignment whose value is a subscript. That set was
  fixed with this protocol.
- Overhead. Wall time of the unmutated script with the hooks installed,
  minus wall time of the same script without them.

## Baselines

Each scored case also asks three guesses for the mutated line.

- Largest row drop. The user line of the mutated-run record with the
  largest positive fraction of rows removed. Ties take the earliest record.
  No drop is a miss.
- Last changed step. The last user line whose operation or row delta
  differs from the clean run.
- Random. A seeded choice among the script's pipeline-call lines. The seed
  is the case id.

If the library does not beat largest-row-drop, the paper says so.

## What is shipped

`manifest.json` holds the slot, the repository URL, the commit, the
dataset location, the dataset SHA-256 once the file is downloaded, and the
mutation is the fault name plus the line `mutate.py` records at run time.
Notebooks and datasets are not copied into this repository unless their
licence allows redistribution. The cache directory is gitignored.

## Amendment 1 (10 October 2026)

Written after pool 1 was run and before any mutation was scored, and before
pool 2 was retrieved.

Pool 1 produced nine files that passed the static rules. Two of them exited 0
after matplotlib, seaborn, and multiprocess were installed. Those two are dev
slots 2 and 3, in the order they qualify: `MrMike92/Grid_Search` `RF.py`, then
`Anwarulh007/AI-based-Email-Sorting-System` `P1.PY`. The other seven are in
`skipped.jsonl` (`does_not_run`): a removed `OneHotEncoder` argument, an
`IndexError`, a classifier rejecting NaN, or an import of streamlit or flask.
Streamlit and flask were not installed. A server does not exit.

Two runnable scripts cannot fill a five-plus-ten split. Pool 2 is the first
100 hits of a second search, same licence, dataset, adapter, and run rules:

    fetch_openml train_test_split accuracy_score extension:py

Saved as `search_2026-10-10_pool2.json`, API order, pages in order. Slots
after dev-3 are filled from pool 2. Pool 2 is not extended. Dev slot 1 is
unchanged.

Pool 2 was then retrieved and walked to the end. Two more development scripts
exited 0, which fills dev-4 and dev-5: `Thanvik931/NeuroCloak`
`fetch_openml_credit_g.py`, then `ktakita1011/MiniKaggle`
`sample_make_titanic_competition.py`. Two held-out scripts exited 0:
`Devanik21/Harmonic-Resonance-Forest` `hrf_conference.py`, then
`nazaninzareirad/SVM-paper` `visuals2.py`. Every other hit in both pools is in
`skipped.jsonl`. No mutation has been scored. `P1.PY`'s CSV is 73 bytes; the
size rule was not in the protocol, so the file stays and the size is stated
here rather than used as a reason to drop it.

## Amendment 2 (10 October 2026)

Written after both earlier pools were exhausted, before any mutation was
scored, and before this pool was retrieved.

Pool 2 ended at two held-out scripts. The target is ten. Pool 3 is the
first 100 hits of:

    "from sklearn.datasets import" train_test_split accuracy_score extension:py

Saved as `search_2026-10-10_pool3.json`, API order. The same licence,
dataset, adapter, and five-minute rules apply. A hit already judged in
pool 1 or pool 2 is `already_in_earlier_pool` and is not judged again.
Pool 3 fills held-out slots only. The development slots stay as they are.
Pool 3 is not extended.

Pool 3 was retrieved and walked to the end. One more held-out script exited 0:
`duckyies/Fuzzy-knn` `fknn.py` (iris and breast cancer, bundled with
scikit-learn). Held-out is three scripts. The other pool 3 hits are in
`skipped.jsonl`. No mutation had been scored when this pool was closed.

## Harness corrections (10 October 2026)

Found on the first development run, fixed before that run was repeated and
before any held-out mutation. The selection rule, the fault list, and the
measures are unchanged.

The clean-run fingerprint was written to the same path as the run report, so
the report replaced it. The comparison then saw an empty operation list and
flagged every later run. The fingerprint now has its own file.

`change_join` was also matching `Thread.join()` / `Process.join()`, which take
no dataframe. A join with no frame, `on`, `how`, `left_on`, or `right_on` is
left alone. `RF.py`'s `t.join()` is therefore not applicable.

## Study 2 (11 October 2026)

Written after `heldout_results/` was locked. That run stays the published
result. Nothing in this section changes it, and those three scripts are not
reused as Study 2 held-out. No Study 2 script has been scored.

Query, as sent to `GET /search/code`, saved as
`search_2026-10-11_study2.json` before any hit from it is judged:

    astype drop train_test_split accuracy_score extension:py

The first 100 hits, two pages of 50, in API order. This pool is not
extended after qualification starts. A file already judged in an earlier
pool is `already_in_earlier_pool`. The first 5 that exit 0 are
development. The next ones that exit 0 are held-out, up to 15.

The first Study 2 pool was judged before any of it was executed. It kept
9 files. That is short of 5 development plus 15 held-out, so a second
query is added before qualification:

    read_csv dropna train_test_split accuracy_score extension:py -filename:app.py

Saved as `search_2026-10-11_study2b.json`. Same rules. Hits already
judged, including the first Study 2 pool, are `already_in_earlier_pool`.
Static judgement of that pool kept 5 new files, 14 in total, still
short of 5 plus 15. A third query is added before qualification:

    get_dummies train_test_split accuracy_score read_csv extension:py -filename:app.py

Saved as `search_2026-10-11_study2c.json`. Same rules. Qualification
of these three pools is closed. None of them is extended or re-queried.

That qualification ran before any Study 2 mutation was scored. Of 20
files that passed the static filter, 6 import a server and were not
executed, 13 were executed and failed, and 1 exited 0
(`EmperialX/BANK-LOAN-CHECK` `fibe.py`, development slot 1). One
runnable script cannot supply 30 scored faults. The failures were
missing local files, missing modules, a timeout, and an encoding
error on stdout. The following four queries are written before any
of them is sent. Each one asks for a dataset the script builds or
loads from scikit-learn, plus two catalogue tokens, so a missing CSV
is not the failure that emptied the first three pools.

    make_classification train_test_split astype accuracy_score extension:py -filename:app.py
    load_breast_cancer train_test_split get_dummies accuracy_score extension:py -filename:app.py
    load_iris train_test_split dropna accuracy_score extension:py -filename:app.py
    make_classification train_test_split get_dummies accuracy_score extension:py -filename:app.py

Saved as `search_2026-10-11_study2d.json` through
`search_2026-10-11_study2g.json`. Same licence, dataset, and
two-fault rules. Hits already judged are `already_in_earlier_pool`.
These four pools are not extended after their qualification starts.
Development stays the first 5 that exit 0, counting the one already
placed. Held-out stays the next that exit 0, up to 15.

Qualification of pools D–G is closed, still before any Study 2
mutation was scored. The four pools added 53 static keeps. Together
with the 20 from pools A–C, 73 files were pending. 8 were servers
and were not executed. 64 were executed. 63 failed. 1 exited 0.
Development is that one script. Held-out is empty. The closed pools
do not contain 10 pipelines, so they cannot supply 30 scored faults.
That shortfall is the result. It is not filled by another query
after this qualification.

A file that imports `streamlit` or `flask` is `server_does_not_exit`.
A server process does not finish, so it is not executed. This is the
same rule as the first study, which left those imports uninstalled.

The bar, checked on 19 October 2026: at least 30 scored faults across at
least 10 pipelines, under a runner that is frozen before that held-out run;
a comparison with mlinspect on the development split; and an overhead figure
from repeated runs that agree in sign.

Rules fixed now:

- Same OSI licences and the same dataset-licence rule as above.
- A hit must contain at least two applicable faults from the catalogue.
  Fewer than two is `too_few_fault_sites` and is counted.
- The unmutated script must finish in 5 minutes with `MPLBACKEND=Agg`.
  Scoring sets that variable. The locked run did not. A qualification
  timeout kills the process tree. Waiting on the child's pipes does not,
  which is how one follow-up script hung the selector.
- Development and held-out are split before any mutation is scored.
  The library may change on the development split only.
- Overhead is the median wall-clock difference of three hooked runs and
  three unhooked runs, plus the sum of recorded `duration_ms`.
- Two coverage numbers are reported. The frozen definition stays. The
  second, framework-call coverage, drops subscript assignments and drops
  calls named `fit`, `predict`, `predict_proba`, `score`, or `astype`
  whose receiver is not a pandas or sklearn name. Constructors of those
  classes stay in the frozen number and are listed separately. The frozen
  number is not replaced by the second one.


