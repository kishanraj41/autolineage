# AutoLineage v0.1.0 🎉

## Automatic ML Data Lineage Tracking

We're excited to announce the first release of AutoLineage!

### What is AutoLineage?

AutoLineage automatically tracks your ML data lineage - from raw data to trained models - **with zero manual logging**.

Just add `import autolineage.auto` to your code and everything is tracked automatically!

### Key Features ✨

- **🔄 Zero Manual Logging** - Automatic tracking via function hooking
- **📊 Beautiful Visualizations** - Interactive HTML and static PNG graphs
- **📋 EU AI Act Compliance** - One-command compliance report generation
- **🪄 Jupyter Support** - Magic commands for notebooks
- **⚡ CLI Interface** - Complete command-line tool
- **🔐 Cryptographic Verification** - SHA-256 hashes for data integrity

### Installation
```bash
pip install autolineage
```

### Quick Start
```python
import autolineage.auto
import pandas as pd

df = pd.read_csv('data.csv')
df_clean = df.dropna()
df_clean.to_csv('clean.csv')

# Lineage tracked automatically! 🎉
```

### What's Included

- Automatic tracking for pandas, numpy, pickle, joblib
- Visual lineage graphs (PNG + interactive HTML)
- CLI tool (`lineage` command)
- EU AI Act compliance reports
- Jupyter magic commands
- Comprehensive documentation

### Documentation

- [README](https://github.com/yourusername/autolineage#readme)
- [QuickStart Guide](https://github.com/yourusername/autolineage/blob/main/docs/quickstart.md)
- [CLI Reference](https://github.com/yourusername/autolineage/blob/main/docs/cli.md)
- [Examples](https://github.com/yourusername/autolineage/tree/main/examples)

### Roadmap

Coming soon:
- MLflow integration
- Git integration
- Column-level lineage
- Data drift detection
- Team collaboration

### Feedback

Found a bug? Have a feature request?
- Open an issue: https://github.com/yourusername/autolineage/issues
- Start a discussion: https://github.com/yourusername/autolineage/discussions

### Citation
```bibtex
@software{autolineage2025,
  author = {Your Name},
  title = {AutoLineage: Automatic ML Data Lineage Tracking},
  year = {2025},
  url = {https://github.com/yourusername/autolineage}
}
```

---

**Thank you for trying AutoLineage!** ⭐

If you find it useful, please star the repository!