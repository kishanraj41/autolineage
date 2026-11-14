"""Incident checks: each one fires on its own fixture and stays quiet on a matching run."""

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from autolineage.checks import capture_run, evaluate, load_run, save_run

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmarks" / "checks" / "cases"
CORPUS_REPRO = Path(
    r"C:\Users\kisha\OneDrive\Documents\Claude\Projects\bussines\corpus\repros"
    r"\repro_003_merge_fanout.py"
)


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


def test_row_conservation_names_the_merge_line():
    current, baseline = _pair("repro_003")
    found = [item for item in evaluate(current, baseline, {}) if item.check == "row_conservation"]
    assert found
    assert found[0].source_line == _line(CASES / "repro_003_fault.py")
    assert found[0].incident_refs == ("SF-002", "SF-018", "SF-022")
    assert "16 -> 20" in found[0].message


def test_corpus_repro_003_merge_fanout_when_present():
    if not CORPUS_REPRO.is_file():
        return
    baseline, error = capture_run(str(CASES / "repro_003_baseline.py"))
    assert error is None
    current, error = capture_run(str(CORPUS_REPRO))
    assert error is None
    found = [item for item in evaluate(current, baseline, {}) if item.check == "row_conservation"]
    assert found
    assert found[0].operation == "merge"


def test_null_rate_after_coerce_names_to_datetime():
    current, baseline = _pair("repro_001")
    found = [item for item in evaluate(current, baseline, {}) if item.check == "null_rate_after_coerce"]
    assert len(found) == 1
    assert found[0].operation == "to_datetime"
    assert found[0].source_line == _line(CASES / "repro_001_fault.py")
    assert "SF-001" in found[0].incident_refs


def test_monotonic_cumulative_names_the_assignment():
    contract = _contract("repro_004.json")
    current, baseline = _pair("repro_004", contract)
    found = evaluate(current, baseline, contract)
    mono = [item for item in found if item.check == "monotonic_cumulative"]
    assert mono
    assert mono[0].source_line == _line(CASES / "repro_004_fault.py")
    assert "Vaccinated_1st" in mono[0].message


def test_unique_keys_reports_a_repeated_id(tmp_path):
    contract = {"keys": ["animal_id"]}
    baseline_path = tmp_path / "base.py"
    fault_path = tmp_path / "fault.py"
    baseline_path.write_text(
        "import pandas as pd\n"
        "df = pd.DataFrame({'animal_id': [1, 2, 3]})\n"
        "df['animal_id'] = [1, 2, 3]\n",
        encoding="utf-8",
    )
    fault_path.write_text(
        "import pandas as pd\n"
        "df = pd.DataFrame({'animal_id': [1, 2, 3]})\n"
        "df['animal_id'] = [1, 1, 3]  # fault\n",
        encoding="utf-8",
    )
    current, baseline = capture_run(str(fault_path), contract)[0], capture_run(str(baseline_path), contract)[0]
    found = [item for item in evaluate(current, baseline, contract) if item.check == "unique_keys_timestamps"]
    assert found
    assert found[0].source_line == 3
    assert "animal_id" in found[0].message


def test_freshness_flags_an_older_max_date():
    contract = _contract("sf036_volume.json")
    base_script = CASES / "sf036_volume_baseline.py"
    stale = (
        "import pandas as pd\n"
        "rows = pd.DataFrame({\n"
        "    'date': pd.to_datetime(['2020-08-01'] * 200),\n"
        "    'source': ['lab_a'] * 100 + ['lab_b'] * 100,\n"
        "})\n"
        "published = rows.dropna()  # fault\n"
    )
    current_path = base_script.with_name("_stale_tmp.py")
    current_path.write_text(stale, encoding="utf-8")
    try:
        baseline, error = capture_run(str(base_script), contract)
        assert error is None
        current, error = capture_run(str(current_path), contract)
        assert error is None
    finally:
        current_path.unlink(missing_ok=True)
    found = [item for item in evaluate(current, baseline, contract) if item.check == "freshness_and_volume"]
    assert any("older than baseline" in item.message for item in found)


def test_volume_flags_a_source_that_shrunk():
    contract = _contract("sf036_volume.json")
    current, baseline = _pair("sf036_volume", contract)
    found = [item for item in evaluate(current, baseline, contract) if item.check == "freshness_and_volume"]
    assert any("lab_b" in item.message for item in found)
    assert found[0].source_line == _line(CASES / "sf036_volume_fault.py")


def test_matching_run_has_no_violations():
    current, _ = capture_run(str(CASES / "repro_003_baseline.py"))
    assert evaluate(current, current, {}) == []


def test_baseline_round_trip(tmp_path):
    records, error = capture_run(str(CASES / "repro_003_baseline.py"))
    assert error is None
    path = tmp_path / "baseline.json"
    save_run(str(path), records, {"keys": ["customer_id"]})
    loaded, contract = load_run(str(path))
    assert contract["keys"] == ["customer_id"]
    assert len(loaded) == len(records)
    assert loaded[0].operation == records[0].operation


def test_cli_exits_nonzero_on_a_violation(tmp_path):
    baseline = tmp_path / "baseline.json"
    script = str(CASES / "repro_003_fault.py")
    base = [sys.executable, "-m", "autolineage.cli"]
    saved = subprocess.run(
        base + ["baseline", str(CASES / "repro_003_baseline.py"), "-o", str(baseline)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert saved.returncode == 0, saved.stderr
    checked = subprocess.run(
        base + ["check", script, "--baseline", str(baseline)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert checked.returncode == 1
    assert "row_conservation" in checked.stdout
    assert "repro_003_fault.py" in checked.stdout


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
    assert recs
    assert recs[-1].metadata["source_line"] == marked
    assert "null_rate" in recs[-1].metadata
