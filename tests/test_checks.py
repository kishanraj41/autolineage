"""Incident checks: each one fires on its own fixture and stays quiet on a matching run."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from autolineage.checks import capture_run, evaluate, load_run, save_run

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmarks" / "checks" / "cases"
CORPUS_REPRO = Path(__file__).parent / "fixtures" / "repro_003_merge_fanout.py"
CLI = [sys.executable, "-m", "autolineage.cli"]


def _contract(name):
    path = ROOT / "benchmarks" / "checks" / "contracts" / name
    return json.loads(path.read_text(encoding="utf-8"))


def _pair(case_id, contract=None):
    baseline, base_error = capture_run(str(CASES / f"{case_id}_baseline.py"), contract)
    current, fault_error = capture_run(str(CASES / f"{case_id}_fault.py"), contract)
    assert base_error is None, base_error
    assert fault_error is None, fault_error
    return current, baseline


def _line(path: Path) -> int:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if "# fault" in line:
            return number
    raise AssertionError(f"no fault line in {path}")


def _script(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return path


def _run(path: Path, contract=None):
    records, error = capture_run(str(path), contract)
    assert error is None, error
    return records


def _only(violations, check):
    return [item for item in violations if item.check == check]


def test_row_conservation_names_the_merge_line():
    current, baseline = _pair("repro_003")
    found = _only(evaluate(current, baseline, {}), "row_conservation")
    assert found
    assert found[0].source_line == _line(CASES / "repro_003_fault.py")
    assert found[0].incident_refs == ("SF-002", "SF-018", "SF-022")
    assert "16 -> 20" in found[0].message


def test_corpus_repro_003_merge_fanout():
    """The published corpus reproduction, against a baseline with unique keys."""
    baseline = _run(CASES / "repro_003_baseline.py")
    current = _run(CORPUS_REPRO)
    found = _only(evaluate(current, baseline, {}), "row_conservation")
    assert found
    assert found[0].operation == "merge"
    assert "16 -> 20" in found[0].message


def test_null_rate_after_coerce_names_to_datetime():
    current, baseline = _pair("repro_001")
    found = _only(evaluate(current, baseline, {}), "null_rate_after_coerce")
    assert len(found) == 1
    assert found[0].operation == "to_datetime"
    assert found[0].source_line == _line(CASES / "repro_001_fault.py")
    assert "SF-001" in found[0].incident_refs


def test_monotonic_cumulative_names_the_assignment():
    contract = _contract("repro_004.json")
    current, baseline = _pair("repro_004", contract)
    mono = _only(evaluate(current, baseline, contract), "monotonic_cumulative")
    assert mono
    assert mono[0].source_line == _line(CASES / "repro_004_fault.py")
    assert "Vaccinated_1st" in mono[0].message


def test_unique_keys_reports_a_repeated_id(tmp_path):
    contract = {"keys": ["animal_id"]}
    baseline = _run(_script(tmp_path, "base.py", """
        import pandas as pd
        df = pd.DataFrame({'animal_id': [1, 2, 3]})
        df['animal_id'] = [1, 2, 3]
    """), contract)
    current = _run(_script(tmp_path, "fault.py", """
        import pandas as pd
        df = pd.DataFrame({'animal_id': [1, 2, 3]})
        df['animal_id'] = [1, 1, 3]
    """), contract)
    found = _only(evaluate(current, baseline, contract), "unique_keys_timestamps")
    assert found
    assert found[0].source_line == 3
    assert "animal_id" in found[0].message


def test_freshness_flags_an_older_max_date(tmp_path):
    contract = _contract("sf036_volume.json")
    baseline = _run(CASES / "sf036_volume_baseline.py", contract)
    current = _run(_script(tmp_path, "stale.py", """
        import pandas as pd
        rows = pd.DataFrame({
            'date': pd.to_datetime(['2020-08-01'] * 200),
            'source': ['lab_a'] * 100 + ['lab_b'] * 100,
        })
        published = rows.dropna()
    """), contract)
    found = _only(evaluate(current, baseline, contract), "freshness_and_volume")
    assert any("older than baseline" in item.message for item in found)


def test_volume_flags_a_source_that_shrunk():
    contract = _contract("sf036_volume.json")
    current, baseline = _pair("sf036_volume", contract)
    found = _only(evaluate(current, baseline, contract), "freshness_and_volume")
    assert any("lab_b" in item.message for item in found)
    assert found[0].source_line == _line(CASES / "sf036_volume_fault.py")


def test_matching_run_has_no_violations():
    current = _run(CASES / "repro_003_baseline.py")
    assert evaluate(current, current, {}) == []


def test_main_guarded_script_is_recorded(tmp_path):
    """The script runs as ``__main__``, so a guarded entry point executes."""
    records = _run(_script(tmp_path, "guarded.py", """
        import pandas as pd

        def main():
            pd.DataFrame({"a": [1.0, None, 3.0]}).dropna()

        if __name__ == "__main__":
            main()
    """))
    assert [rec.operation for rec in records] == ["dropna"]
    assert records[0].metadata["source_line"] == 4


def test_script_sees_its_arguments(tmp_path):
    script = _script(tmp_path, "args.py", """
        import sys
        import pandas as pd
        pd.DataFrame({"a": range(10)}).head(int(sys.argv[1]))
    """)
    records, error = capture_run(str(script), None, ["4"])
    assert error is None, error
    assert records[0].rows_after == 4
    assert str(tmp_path) not in sys.path


def test_a_load_that_returns_fewer_rows_is_flagged(tmp_path):
    """The SF-002 shape: the file is read short and every later step is unchanged."""
    full = tmp_path / "full.csv"
    short = tmp_path / "short.csv"
    full.write_text("id\n" + "\n".join(str(i) for i in range(100)), encoding="utf-8")
    short.write_text("id\n" + "\n".join(str(i) for i in range(60)), encoding="utf-8")
    body = """
        import pandas as pd
        df = pd.read_csv(r"{path}")
        out = df.sort_values("id")
    """
    baseline = _run(_script(tmp_path, "base.py", body.format(path=full)))
    current = _run(_script(tmp_path, "cut.py", body.format(path=short)))
    found = evaluate(current, baseline, {})
    assert [item.check for item in found] == ["row_conservation"]
    assert found[0].operation == "read_csv"
    assert found[0].source_line == 2
    assert "loaded 60 rows, baseline 100" in found[0].message
    # A load that grew is new data, not a loss.
    assert evaluate(baseline, current, {}) == []


def test_an_inserted_step_does_not_shift_the_others(tmp_path):
    frame = 'df = pd.DataFrame({"a": [1.0, None, 3.0, 4.0], "b": [1.0, 2.0, None, 4.0]})'
    baseline = _run(_script(tmp_path, "base.py", f"""
        import pandas as pd
        {frame}
        one = df.dropna(subset=["a"])
        two = one.dropna(subset=["b"])
    """))
    current = _run(_script(tmp_path, "inserted.py", f"""
        import pandas as pd
        {frame}
        zero = df.dropna(how="all")
        one = zero.dropna(subset=["a"])
        two = one.dropna(subset=["b"])
    """))
    assert evaluate(current, baseline, {}) == []


def test_an_inserted_filter_that_drops_rows_is_still_flagged(tmp_path):
    frame = 'df = pd.DataFrame({"a": [1.0, None, 3.0, 4.0], "b": [1.0, 2.0, 3.0, 4.0]})'
    baseline = _run(_script(tmp_path, "base.py", f"""
        import pandas as pd
        {frame}
        one = df.dropna(subset=["a"])
    """))
    current = _run(_script(tmp_path, "filtered.py", f"""
        import pandas as pd
        {frame}
        small = df.head(2)
        one = small.dropna(subset=["a"])
    """))
    found = _only(evaluate(current, baseline, {}), "row_conservation")
    assert found[0].operation == "head"
    assert found[0].source_line == 3
    assert "no baseline step" in found[0].message


def test_measuring_a_date_adds_no_records(tmp_path):
    contract = {"date_column": "date", "source_column": "source"}
    records = _run(_script(tmp_path, "dated.py", """
        import pandas as pd
        rows = pd.DataFrame({"date": ["2020-08-04"] * 4, "source": ["a", "a", "b", "b"]})
        kept = rows.dropna()
        again = kept.sort_values("date")
    """), contract)
    assert [rec.operation for rec in records] == ["dropna", "sort_values"]
    assert records[0].metadata["max_date"].startswith("2020-08-04")
    assert records[0].metadata["source_counts"] == {"a": 2, "b": 2}


def test_coercion_of_a_list_and_a_series_is_recorded(tmp_path):
    records = _run(_script(tmp_path, "shapes.py", """
        import pandas as pd
        df = pd.DataFrame({"n": ["1", "x"]})
        idx = pd.to_datetime(["2024-01-01", "bad"], errors="coerce")
        arr = pd.to_numeric(["1", "x"], errors="coerce")
        text = df["n"].astype("string")
    """))
    seen = [(rec.operation, rec.metadata.get("source_line"), rec.metadata.get("null_rate"))
            for rec in records]
    assert seen == [("to_datetime", 3, 0.5), ("to_numeric", 4, 0.5), ("astype", 5, 0.0)]
    assert records[2].parameters["column"] == "n"


def test_metric_drop_fails_the_check(tmp_path):
    body = """
        import pandas as pd
        from sklearn.metrics import accuracy_score
        truth = pd.Series([1, 1, 1, 1, 0, 0, 0, 0])
        score = accuracy_score(truth, {predicted})
    """
    baseline = _run(_script(tmp_path, "good.py", body.format(predicted="[1, 1, 1, 1, 0, 0, 0, 0]")))
    current = _run(_script(tmp_path, "bad.py", body.format(predicted="[1, 1, 0, 0, 0, 0, 1, 1]")))
    found = evaluate(current, baseline, {})
    assert [item.check for item in found] == ["metric_change"]
    assert found[0].source_line == 4
    assert "accuracy_score dropped from 1.0000 to 0.5000" in found[0].message
    assert found[0].format().endswith("(-50.0%)")
    assert evaluate(baseline, current, {}) == []


def test_baseline_round_trip(tmp_path):
    records = _run(CASES / "repro_003_baseline.py")
    path = tmp_path / "baseline.json"
    save_run(str(path), records, {"keys": ["customer_id"]})
    loaded, contract = load_run(str(path))
    assert contract["keys"] == ["customer_id"]
    assert len(loaded) == len(records)
    assert loaded[0].operation == records[0].operation


def test_baseline_file_holds_no_machine_paths(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "rows.csv").write_text("id\n1\n2\n", encoding="utf-8")
    script = _script(tmp_path, "load.py", """
        import pandas as pd
        from pathlib import Path
        df = pd.read_csv(Path(__file__).parent / "data" / "rows.csv")
        out = df.sort_values("id")
    """)
    baseline = tmp_path / "out" / "baseline.json"
    saved = subprocess.run(CLI + ["baseline", str(script), "-o", str(baseline)],
                           cwd=ROOT, capture_output=True, text=True, check=False)
    assert saved.returncode == 0, saved.stderr
    text = baseline.read_text(encoding="utf-8")
    assert str(tmp_path) not in text
    assert str(tmp_path).replace("\\", "\\\\") not in text
    records, _ = load_run(str(baseline))
    assert records[0].metadata["filepath"] == "data/rows.csv"
    assert records[0].metadata["source_file"] == "load.py"
    checked = subprocess.run(CLI + ["check", str(script), "--baseline", str(baseline)],
                             cwd=ROOT, capture_output=True, text=True, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "no violations (2 records)" in checked.stdout


def test_cli_exits_nonzero_on_a_violation(tmp_path):
    baseline = tmp_path / "baseline.json"
    saved = subprocess.run(
        CLI + ["baseline", str(CASES / "repro_003_baseline.py"), "-o", str(baseline)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert saved.returncode == 0, saved.stderr
    checked = subprocess.run(
        CLI + ["check", str(CASES / "repro_003_fault.py"), "--baseline", str(baseline)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert checked.returncode == 1
    assert "row_conservation" in checked.stdout
    assert "repro_003_fault.py" in checked.stdout


def test_cli_refuses_a_run_that_recorded_nothing(tmp_path):
    """A script that never reaches pandas must not pass as 'no violations'."""
    empty = _script(tmp_path, "empty.py", """
        def main():
            import pandas as pd
            pd.DataFrame({"a": [1.0, None]}).dropna()
    """)
    baseline = tmp_path / "baseline.json"
    saved = subprocess.run(CLI + ["baseline", str(empty), "-o", str(baseline)],
                           cwd=ROOT, capture_output=True, text=True, check=False)
    assert saved.returncode == 2
    assert "nothing to check" in saved.stderr
    assert not baseline.exists()

    good = tmp_path / "good.json"
    subprocess.run(CLI + ["baseline", str(CASES / "repro_003_baseline.py"), "-o", str(good)],
                   cwd=ROOT, capture_output=True, text=True, check=True)
    checked = subprocess.run(CLI + ["check", str(empty), "--baseline", str(good)],
                             cwd=ROOT, capture_output=True, text=True, check=False)
    assert checked.returncode == 2
    assert "no violations" not in checked.stdout


def test_cli_passes_arguments_after_the_separator(tmp_path):
    script = _script(tmp_path, "args.py", """
        import sys
        import pandas as pd
        pd.DataFrame({"a": range(10)}).head(int(sys.argv[1]))
    """)
    baseline = tmp_path / "baseline.json"
    saved = subprocess.run(CLI + ["baseline", str(script), "-o", str(baseline), "--", "10"],
                           cwd=ROOT, capture_output=True, text=True, check=False)
    assert saved.returncode == 0, saved.stderr
    checked = subprocess.run(CLI + ["check", str(script), "--baseline", str(baseline), "--", "6"],
                             cwd=ROOT, capture_output=True, text=True, check=False)
    assert checked.returncode == 1
    assert "rows 10 -> 6, baseline 10 -> 10" in checked.stdout


def test_cli_records_a_child_process_the_script_starts(tmp_path):
    script = _script(tmp_path, "child.py", """
        import multiprocessing
        import pandas as pd

        def work():
            pd.DataFrame({"a": [1, None]}).dropna()

        if __name__ == "__main__":
            pd.DataFrame({"a": [1, None]}).dropna()
            proc = multiprocessing.Process(target=work)
            proc.start()
            proc.join()
    """)
    baseline = tmp_path / "baseline.json"
    saved = subprocess.run(CLI + ["baseline", str(script), "-o", str(baseline)],
                           cwd=ROOT, capture_output=True, text=True, check=False)
    assert saved.returncode == 0, saved.stderr
    lines = sorted(rec["metadata"]["source_line"]
                   for rec in json.loads(baseline.read_text(encoding="utf-8"))["records"])
    assert lines == [5, 8]


def test_astype_null_rate_is_recorded():
    import inspect
    from autolineage.core.tracker import UnifiedTracker
    from autolineage.hooks.registry import HookRegistry

    tracker = UnifiedTracker()
    registry = HookRegistry()
    registry.install_all(tracker)
    try:
        frame = pd.DataFrame({"n": [1.0, None, 3.0]})
        marked = inspect.currentframe().f_lineno + 1
        frame.astype({"n": "float64"})
    finally:
        registry.uninstall_all()
    recs = [rec for rec in tracker.records if rec.operation == "astype"]
    assert len(recs) == 1
    assert recs[0].metadata["source_line"] == marked
    assert recs[0].metadata["null_rate"] == pytest.approx(1 / 3)
