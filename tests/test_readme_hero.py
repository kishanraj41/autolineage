"""The first Python block in the README runs without any file the user has to create."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_hero_runs_in_a_clean_directory(tmp_path):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"```python\n(.*?)```", readme, re.S)
    assert match, "README has no Python block"
    script = tmp_path / "hero.py"
    script.write_text(match.group(1), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert (tmp_path / "trace.html").is_file()
