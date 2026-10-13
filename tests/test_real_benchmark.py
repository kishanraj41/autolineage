"""Mutations preserve line numbers, and excluded faults stay out of the rate."""

import ast

from benchmarks.real.mutate import FAULTS, bump_random_state, mutate
from benchmarks.real.score import (
    constructor_lines, framework_call_lines, metric_changed,
    pipeline_call_lines, score_case, summarize,
)

FIXTURE = """import pandas as pd
from sklearn.model_selection import train_test_split
df = pd.read_csv("a.csv")
df = df[df["x"] > 10]
df = df.merge(other, on=["a", "b"], how="left")
df = df[["a", "b", "c"]]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)
sc.fit_transform(X_train)
df = pd.get_dummies(df, drop_first=True)
df = df.drop_duplicates()
df = df.sample(frac=0.5, random_state=1)
df["x"] = df["x"].astype("float")
y = df["y"]
"""


def test_thread_join_is_not_a_dataframe_join():
    source = "for t in threads:\n    t.join()\n"
    assert mutate(source, "change_join") is None


def test_every_fault_parses_and_keeps_line_numbers():
    original_lines = FIXTURE.splitlines()
    for fault in FAULTS:
        mutation = mutate(FIXTURE, fault)
        assert mutation is not None, fault
        ast.parse(mutation.source)
        edited = mutation.source.splitlines()
        assert len(edited) == len(original_lines)
        assert edited[mutation.line - 1] != original_lines[mutation.line - 1]


def test_insert_filter_does_not_move_the_next_line():
    mutation = mutate(FIXTURE, "insert_filter")
    assert mutation.line == 3
    assert ".iloc[::2]" in mutation.source.splitlines()[2]
    assert mutation.source.splitlines()[3] == FIXTURE.splitlines()[3]


def test_multiline_call_keeps_later_lines():
    source = 'df = pd.read_csv(\n    "a.csv"\n)\nprint("after")\n'
    mutation = mutate(source, "insert_filter")
    assert mutation.line == 3
    assert mutation.source.splitlines()[0] == "df = pd.read_csv("
    assert mutation.source.splitlines()[3] == 'print("after")'
    assert ".iloc[::2]" in mutation.source.splitlines()[2]


def test_missing_pattern_is_not_applicable():
    assert mutate("x = 1\n", "insert_filter") is None
    assert mutate("x = 1\n", "remove_dedup") is None


def test_bump_random_state_changes_the_first_one_only():
    bumped = bump_random_state(FIXTURE)
    assert "random_state=1" in bumped
    assert "random_state=0" not in bumped
    assert bumped.count("random_state=1") == 2


def test_no_metric_change_stays_out_of_the_rate(tmp_path):
    clean_script = tmp_path / "pipe.py"
    mutated_script = tmp_path / "pipe.mutated.py"
    clean_script.write_text("x = 1\n")
    mutated_script.write_text(FIXTURE)
    clean = _report(clean_script, metrics={"accuracy_score": 0.5})
    unchanged = _report(mutated_script, metrics={"accuracy_score": 0.5})
    changed = _report(
        mutated_script,
        metrics={"accuracy_score": 0.2},
        anomalies=[{"severity": "warning", "operation": "filter"}],
        ranking=[{"source_file": str(mutated_script), "source_line": 4, "operation": "filter"}],
        records=[{
            "operation": "filter", "category": "transform",
            "rows_before": 100, "rows_after": 10,
            "source_file": str(mutated_script), "source_line": 4,
        }],
    )
    excluded = score_case(
        fault="change_filter_threshold", mutated_line=4,
        clean_script=str(clean_script), mutated_script=str(mutated_script),
        case_id="case-excluded", clean=clean, mutated=unchanged,
        unmutated_rerun=None, wall_without_hooks_s=1.0, mutated_source=FIXTURE,
    )
    scored = score_case(
        fault="change_filter_threshold", mutated_line=4,
        clean_script=str(clean_script), mutated_script=str(mutated_script),
        case_id="case-scored", clean=clean, mutated=changed,
        unmutated_rerun={"status": "ok", "anomalies": []},
        wall_without_hooks_s=1.0, mutated_source=FIXTURE,
    )
    assert excluded["status"] == "no_metric_change"
    assert excluded["detected"] is None
    assert scored["status"] == "scored"
    assert scored["detected"] is True
    assert scored["top1"] is True
    assert scored["top3"] is True
    assert scored["baseline_largest_row_drop"] is True
    assert scored["false_positive"] is False
    summary = summarize([excluded, scored])
    assert summary["n_scored"] == 1
    assert summary["n_no_metric_change"] == 1
    assert summary["detection"] == 1.0


def test_framework_coverage_drops_subscripts_and_foreign_methods():
    source = (
        "import pandas as pd\n"
        "from sklearn.svm import SVC\n"
        "df = pd.read_csv('a.csv')\n"
        "y = df['y']\n"
        "model = SVC()\n"
        "model.fit(X, y)\n"
        "model.predict(X)\n"
        "df['x'] = df['x'].astype('float')\n"
    )
    frozen = pipeline_call_lines(source)
    framework = framework_call_lines(source)
    assert 4 in frozen and 4 not in framework
    assert {6, 7, 8} <= frozen
    assert {6, 7, 8}.isdisjoint(framework)
    assert 3 in framework and 5 in framework
    assert constructor_lines(source) == [5]


def test_metric_eps_ignores_noise():
    assert metric_changed({"accuracy_score": 1.0}, {"accuracy_score": 1.0 + 1e-12}) is False
    assert metric_changed({"accuracy_score": 0.8}, {"accuracy_score": 0.5}) is True
    assert metric_changed({}, {}) is False


def _report(script, *, metrics, anomalies=None, ranking=None, records=None):
    return {
        "status": "ok",
        "wall_s": 2.0,
        "metrics": metrics,
        "anomalies": anomalies or [],
        "ranking": ranking or [],
        "records": records or [],
    }
