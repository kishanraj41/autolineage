# QuickStart Guide

Get started with AutoLineage in 5 minutes!

## Installation
```bash
pip install autolineage
```

## Three Ways to Use AutoLineage

### 1. Automatic Tracking (Recommended)

The easiest way - just import and everything is tracked:
```python
import autolineage.auto
import pandas as pd

# Your normal code - everything tracked automatically!
df = pd.read_csv('data.csv')
df_clean = df.dropna()
df_clean.to_csv('clean_data.csv')

# View what was tracked
from autolineage.auto import get_summary
summary = get_summary()
print(f"Tracked {summary['datasets_count']} datasets")
```

### 2. CLI Interface

Track any Python script from the command line:
```bash
# Track your pipeline
lineage track my_pipeline.py

# View summary
lineage summary

# Generate visualization
lineage show --format html --output graph.html

# Generate compliance report
lineage report --format markdown
```

### 3. Manual API

For fine-grained control:
```python
from autolineage import DatasetTracker
from autolineage.hooks import enable_hooks

# Create tracker
tracker = DatasetTracker('my_lineage.db')
tracker.start_run('my_experiment')

# Enable automatic hooks
enable_hooks(tracker)

# Your data science code here...
import pandas as pd
df = pd.read_csv('data.csv')
df.to_csv('output.csv')

# End tracking
tracker.end_run()
tracker.close()
```

## Jupyter Notebooks

AutoLineage works seamlessly in Jupyter:
```python
# Load extension
%load_ext autolineage

# Start tracking
%lineage_start

# Your code here...
import pandas as pd
df = pd.read_csv('data.csv')
df.to_csv('output.csv')

# View results
%lineage_summary
%lineage_show

# Generate report
%lineage_report
```

## What Gets Tracked

AutoLineage automatically tracks:

- **pandas**: read_csv, to_csv, read_parquet, to_parquet, read_json, to_json, etc.
- **numpy**: load, save, loadtxt, savetxt
- **pickle**: dump, load
- **joblib**: dump, load (if installed)

## Next Steps

- See [examples/](../examples/) for complete working examples
- Read [CLI Guide](cli.md) for all command-line options
- Check [API Reference](api.md) for detailed documentation
- View [Compliance Guide](compliance.md) for EU AI Act reporting