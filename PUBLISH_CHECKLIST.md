# PyPI Publish Checklist — AutoLineage v0.3.0

**DO NOT run these until Phase 1 (local verification) passes.**

---

## Pre-Publish Verification

Run each of these in PowerShell. All must succeed.

### 1. All tests pass

```powershell
cd C:\Users\kisha\OneDrive\Documents\AI\autolineage
pytest tests/test_v2.py -v
```

Expected: **36 passed**.

### 2. Package imports cleanly

```powershell
python -c "import autolineage; print(autolineage.__version__)"
```

Expected: **0.3.0**

### 3. Pipeline demo works

```powershell
python paper\case_study_pipeline.py 2>&1 | Select-Object -Last 5
```

Expected: root-cause output pointing at the filter.

### 4. No leftover debug prints

```powershell
Select-String -Path autolineage\*.py,autolineage\**\*.py -Pattern "print\(" | Where-Object {$_.Line -notmatch "^\s*#"}
```

Expected: Only the one print in `auto.py` announcing hook count. If you see others, flag them to me.

---

## If All Pass: Publish to PyPI

### Step 1: Update version in pyproject.toml

```powershell
# Open pyproject.toml and ensure version = "0.3.0"
code pyproject.toml
```

### Step 2: Update CHANGELOG

Create `CHANGELOG.md` at repo root:

```markdown
# Changelog

## 0.3.0 — 2026-04-17

### Breaking changes
- `auto.py` replaced with plugin-based architecture. Legacy hooks kept for backward compatibility.

### New features
- Plugin architecture (`BaseHookProvider`) for extensibility
- 288 hooks across pandas, sklearn, PySpark (up from 55 in v0.2.0)
- `LineageAnalyzer` with anomaly detection and root-cause localization
- Depth-counter reentrancy guard eliminates internal library call noise
- `UnifiedTracker.get_timing_profile()` for bottleneck identification
- Content-hash auto-population on all records (SHA-256)

### Bug fixes
- Write hooks no longer crash with keyword path arguments
- Reload-safe state prevents duplicate hooks on `importlib.reload()`
- Double `install_all()` is idempotent
- Pipeline correctly shows inner component operations while suppressing internal calls

### Quality
- 36 automated tests (all passing)
- Tested against pandas 2.x/3.x, scikit-learn 1.x, PySpark 3.x/4.x
```

### Step 3: Build the distribution

```powershell
# Install build tools
pip install --upgrade build twine

# Clean old builds
Remove-Item -Recurse -Force dist, build, *.egg-info -ErrorAction SilentlyContinue

# Build
python -m build
```

Expected: `dist/` contains `autolineage-0.3.0-py3-none-any.whl` and `autolineage-0.3.0.tar.gz`.

### Step 4: Verify the distribution

```powershell
# Check metadata
python -m twine check dist/*
```

Expected: **PASSED** for both files.

### Step 5: Test install in a fresh venv

```powershell
# Create fresh venv
python -m venv test_install_env
test_install_env\Scripts\Activate.ps1

# Install from your dist
pip install dist/autolineage-0.3.0-py3-none-any.whl

# Test import
python -c "import autolineage; print('OK', autolineage.__version__)"

# Deactivate and clean up
deactivate
Remove-Item -Recurse -Force test_install_env
```

Expected: `OK 0.3.0`.

### Step 6: Upload to TestPyPI first (sanity check)

```powershell
# Upload to TEST PyPI (not real PyPI)
python -m twine upload --repository testpypi dist/*
```

You'll need a TestPyPI account token. Get one at https://test.pypi.org/manage/account/token/

Test install from TestPyPI:

```powershell
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ autolineage==0.3.0
```

If that installs cleanly, you're safe to publish to real PyPI.

### Step 7: Upload to real PyPI

```powershell
python -m twine upload dist/*
```

You'll need your PyPI token. Get one at https://pypi.org/manage/account/token/

### Step 8: Verify it's live

```powershell
# Wait 60 seconds, then:
pip install --upgrade autolineage
python -c "import autolineage; print(autolineage.__version__)"
```

Check the PyPI page: https://pypi.org/project/autolineage/

### Step 9: Tag the release in GitHub

```powershell
git tag v0.3.0 -m "Release v0.3.0 - plugin architecture, analyzer, 4 bug fixes"
git push origin v0.3.0
```

---

## If Anything Fails

**Do not panic. Do not publish the broken version.**

Common failures:

| Error | Fix |
|---|---|
| `ImportError` when testing dist | Check `pyproject.toml` packages config includes `autolineage*` |
| Twine check fails on metadata | Usually a missing field in `pyproject.toml` — paste error to me |
| TestPyPI upload succeeds but install fails | Usually dependency version pinning issue in `dependencies` |
| 403 Forbidden from PyPI | Token scope wrong — generate a new one with "Entire account" scope |

Paste any error to me and I'll diagnose.

---

## After Successful Publish

1. Update README badge: `![PyPI version](https://img.shields.io/pypi/v/autolineage)`
2. Post on Twitter/LinkedIn (see `recruitment.md`)
3. Start recruiting for user study
