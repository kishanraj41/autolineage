# Contributing to AutoLineage

Thanks for your interest in improving AutoLineage. Bug reports, feature requests, and
pull requests are all welcome.

## Reporting bugs and requesting features

Please open an issue on the [issue tracker](https://github.com/kishanraj41/autolineage/issues).
For a bug, a good report includes:

- what you ran (a minimal pandas / scikit-learn / PySpark snippet if possible),
- the AutoLineage version (`pip show autolineage`) and your Python and framework versions,
- what you expected the lineage or the analyzer to report, and what it reported instead.

If the tool localized the wrong operation for a regression you understand, that is one of
the most useful reports we can get: please include the operation you expected and the one
it named.

## Development setup

```bash
git clone https://github.com/kishanraj41/autolineage
cd autolineage
pip install -e ".[dev]"
pytest tests/
```

## Pull requests

1. Open an issue first for anything larger than a small fix, so we can agree on the approach.
2. Create a branch, make focused commits, and keep unrelated changes out of the PR.
3. Add or update tests for the behavior you change. All tests must pass locally and in CI.
4. Keep the public API stable, or call out breaking changes explicitly in the PR description.
5. Run the formatter/linter if the project defines one before pushing.

## Adding support for a new library

AutoLineage uses a plugin architecture: each framework is a single hook-provider file.
To add one:

1. Create `autolineage/hooks/your_lib_hooks.py`.
2. Subclass `BaseHookProvider`.
3. Implement `install(tracker)` and `uninstall()`.
4. Register the provider in `autolineage/hooks/registry.py`.
5. Add tests and open a PR.

See `autolineage/hooks/pandas_io.py` for the smallest working example.

## Code of conduct

By participating you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).
