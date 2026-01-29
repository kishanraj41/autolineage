# AutoLineage

**Automatic ML Data Lineage Tracking**

Track your data lineage automatically - from raw data to trained models - without manual logging.

## 🚀 Quick Start

## 🎯 Three Ways to Use AutoLineage

### 1. Automatic Tracking (Easiest)

Just import and everything is tracked automatically:
```python
import autolineage.auto
import pandas as pd

df = pd.read_csv('data.csv')  # Tracked!
df_clean = df.dropna()
df_clean.to_csv('clean.csv')  # Tracked!
```

### 2. CLI Tracking

Track any Python script:
```bash
lineage track my_pipeline.py
lineage show --output graph.png
lineage summary
```

### 3. Manual API

Fine-grained control:
```python
from autolineage import DatasetTracker

tracker = DatasetTracker()
tracker.start_run()

# Your code here...

tracker.end_run()
```
## 📓 Jupyter Notebook Support

AutoLineage works seamlessly in Jupyter notebooks with magic commands:
```python
# Load the extension
%load_ext autolineage

# Start tracking
%lineage_start

# Your normal data science code
import pandas as pd
df = pd.read_csv('data.csv')
df_clean = df.dropna()
df_clean.to_csv('clean.csv')

# View lineage
%lineage_summary
%lineage_show  # Interactive graph in notebook!

# Generate compliance report
%lineage_report

# Stop tracking
%lineage_stop
```

### Cell Magic

Track specific cells:
```python
%%lineage_track
# Everything in this cell is tracked
df = pd.read_csv('input.csv')
df.to_csv('output.csv')
```

See `examples/jupyter_demo.ipynb` for a complete demo!

## 📊 Visualizations

AutoLineage generates beautiful lineage graphs:

- **Static PNG** - High-resolution images for papers/reports
- **Interactive HTML** - Explore your data flow in the browser
```bash
lineage show --format html --output graph.html
```

## 🚀 What's Tracked

- ✅ pandas (read_csv, to_csv, read_parquet, etc.)
- ✅ numpy (load, save, loadtxt, savetxt)
- ✅ pickle (dump, load)
- ✅ joblib (dump, load)
- ✅ Automatic lineage relationships
- ✅ File hashes for integrity
- ✅ Timestamps and metadata

```bash
pip install autolineage
```
```python
from autolineage import DatasetTracker

# Create tracker
tracker = DatasetTracker()
tracker.start_run()

# Your normal data science code
import pandas as pd
df = pd.read_csv('data.csv')
df_clean = df.dropna()
df_clean.to_csv('clean.csv')

# Track the transformation
tracker.track_transformation(
    source_files=['data.csv'],
    target_files=['clean.csv'],
    function_name='dropna'
)

tracker.end_run()
```

## ✨ Features

- **Zero Manual Logging** - Track lineage automatically
- **Visual Graphs** - See your data flow from source to model
- **EU AI Act Compliant** - Generate compliance reports instantly
- **Multi-Environment** - Works in Jupyter, Python scripts, CLI
- **Lightweight** - SQLite backend, no complex setup

## 📊 What Gets Tracked

- ✅ Dataset files (CSV, Parquet, JSON, pickle)
- ✅ Data transformations and operations
- ✅ File hashes for integrity verification
- ✅ Full lineage graph (source → transformations → output)
- ✅ Timestamps and metadata

## 🎯 Use Cases

- **Research Reproducibility** - Recreate experiments from months ago
- **Compliance** - EU AI Act, GDPR, audit requirements
- **Debugging** - Trace model issues back to data sources
- **Collaboration** - Share complete data provenance with team

## 📖 Documentation

See `/examples` folder for more examples:
- `quickstart.py` - Get started in 60 seconds
- `basic_test.py` - Complete tracking example
- `inspect_db.py` - View database contents

## 🛠️ Development Status

**Current Version:** 0.1.0 (Alpha)

Day 1 ✅ Complete:
- SQLite database schema
- File tracking with SHA256 hashing
- Basic lineage graph generation
- Python API

Coming Soon:
- Automatic pandas/numpy hooking
- Visual graph visualization
- CLI interface (`lineage track script.py`)
- EU AI Act compliance reports
- Web UI

## 🤝 Contributing

This is a research project being developed for a PhD in AI. 

Feedback, issues, and PRs welcome!

## 📄 License

MIT License

## 🙋 Author

Built by Kishan Raj VG as part of PhD research on ML reproducibility.