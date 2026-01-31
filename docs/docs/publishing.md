# Publishing to PyPI

Instructions for publishing AutoLineage to PyPI.

## Prerequisites

1. PyPI account: https://pypi.org/account/register/
2. TestPyPI account: https://test.pypi.org/account/register/
3. API tokens configured

## Setup API Tokens

Create `~/.pypirc`:
```ini
[pypi]
username = __token__
password = pypi-YOUR_API_TOKEN_HERE

[testpypi]
username = __token__
password = pypi-YOUR_TESTPYPI_TOKEN_HERE
```

## Build Package
```bash
# Clean old builds
rm -rf dist/ build/ *.egg-info

# Build
python -m build

# Verify
twine check dist/*
```

## Test on TestPyPI First
```bash
# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Test installation
pip install --index-url https://test.pypi.org/simple/ autolineage
```

## Publish to PyPI
```bash
# Upload to PyPI
twine upload dist/*

# Test installation
pip install autolineage
```

## Post-Release Checklist

- [ ] Create GitHub release
- [ ] Update version in pyproject.toml
- [ ] Update CHANGELOG.md
- [ ] Tag commit: `git tag v0.1.0`
- [ ] Push tags: `git push --tags`

## Version Bumping

For next release:

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Commit changes
4. Create git tag
5. Build and publish