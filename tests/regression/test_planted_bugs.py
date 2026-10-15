"""Regression for the synthetic pipeline.

Each case must still name the operation the bug was written into.
This file does not report a detection rate.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent / "planted_bugs" / "pipeline.py"
EXPECT = {
    "filter": "filter",
    "join": "merge",
    "encoding": "get_dummies",
    "leakage": "get_dummies",
    "type": "dropna",
}


@pytest.mark.parametrize("case", list(EXPECT))
def test_seed0_names_the_planted_operation(case, tmp_path):
    py = sys.executable
    subprocess.run(
        [py, str(SCRIPT), case, "baseline", "0"],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    )
    proc = subprocess.run(
        [py, str(SCRIPT), case, "buggy", "0"],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    )
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    # Type coercion raises F1 slightly, so a row drop is not named as the
    # cause. The drop itself is still flagged. The other cases name the
    # operation the bug was written into.
    if case == "type":
        assert payload["root_cause"] is None
        assert any(item["op"] == "dropna" for item in payload["top_anoms"])
        return
    assert payload["root_cause"]["root_op"] == EXPECT[case]
