# AutoLineage 

**Automatic ML Data Lineage Tracking**

Track your data lineage automatically - from raw data to trained models - without manual logging.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Quick Start
```bash
pip install autolineage
```
```python
import autolineage.auto
import pandas as pd

# Your normal code - everything tracked automatically!
df = pd.read_csv('data.csv')
df_clean = df.dropna()
df_clean.to_csv('clean.csv')

# That's it! Lineage tracked automatically 
```

## Features

- **Zero Manual Logging** - Track lineage automatically with zero code changes
- **Visual Graphs** - Beautiful interactive and static lineage visualizations
- **EU AI Act Compliant** - Generate compliance reports instantly
- **Jupyter Support** - Magic commands for notebooks
- **Multi-Environment** - Works in Jupyter, Python scripts, CLI
- **Lightweight** - SQLite backend, no complex setup
- **Cryptographic Verification** - SHA-256 hashes for data integrity

## Three Ways to Use

### 1️⃣ Automatic (Recommended)
```python
import autolineage.auto

# Just write normal pandas/numpy code
# Everything is tracked automatically!
```

### 2️⃣ CLI
```bash
lineage track my_pipeline.py
lineage show --format html
lineage report
```

### 3️⃣ Jupyter Magic
```python
%load_ext autolineage
%lineage_start

# Your code...

%lineage_show
%lineage_report
```

## What Gets Tracked

AutoLineage automatically hooks into:

| Library | Functions |
|---------|-----------|
| **pandas** | read_csv, to_csv, read_parquet, to_parquet, read_json, to_json, read_excel, to_excel, read_pickle, to_pickle |
| **numpy** | load, save, loadtxt, savetxt |
| **pickle** | dump, load |
| **joblib** | dump, load |

**Plus:** Automatic lineage relationships between files!

## Visualizations

Generate beautiful lineage graphs:
```bash
# Interactive HTML
lineage show --format html --output graph.html

# Static PNG
lineage show --format png --output graph.png
```

Features:
- Color-coded by file type
- Hover for details
- Click to explore
- Export for presentations

## EU AI Act Compliance

Generate compliance reports with one command:
```bash
lineage report --format markdown
```

Includes:
- Complete data inventory with SHA-256 hashes
- All transformation operations documented
- Full lineage graph with verification
- Reproducibility instructions
- Regulatory compliance statement

Perfect for:
- EU AI Act Article 10 requirements
- Model governance and auditing
- Research reproducibility
- Team collaboration

## CLI Reference
```bash
lineage track SCRIPT      # Track a Python script
lineage show              # Visualize lineage graph
lineage summary           # Show statistics
lineage report            # Generate compliance report
lineage clear             # Delete database
```

See [docs/cli.md](docs/cli.md) for complete reference.

## Jupyter Notebook
```python
%load_ext autolineage
%lineage_start

import pandas as pd
df = pd.read_csv('data.csv')
df.to_csv('output.csv')

%lineage_summary          # Show stats
%lineage_show             # Display graph
%lineage_report           # Generate report
```

See [examples/jupyter_demo.ipynb](examples/jupyter_demo.ipynb) for complete demo.

## Documentation

- [QuickStart Guide](docs/quickstart.md) - Get started in 5 minutes
- [CLI Reference](docs/cli.md) - Complete command-line guide
- [Compliance Guide](docs/compliance.md) - EU AI Act reporting
- [Examples](examples/) - Working code samples

## Use Cases

### Research Reproducibility
Track every step from raw data to published results. Never wonder "which dataset did I use?" again.

### ML Model Governance
Automatic compliance documentation for regulated industries. EU AI Act ready.

### Team Collaboration
Share complete data provenance with your team. Everyone knows exactly what transformations were applied.

### Debugging
Trace model issues back to data sources instantly. Full audit trail included.

## Architecture
```
Raw Data → [Transformation 1] → Intermediate → [Transformation 2] → Model
   ↓              ↓                  ↓                ↓              ↓
Tracked    Logged & Hashed    Tracked     Logged & Hashed    Tracked
```

- **SQLite Database** - Portable, zero-config storage
- **Function Hooking** - Automatic tracking via monkey-patching
- **Cryptographic Hashing** - SHA-256 for data integrity
- **Graph Generation** - NetworkX for lineage DAG

## Contributing

This is a research project being developed for a PhD in AI.

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

Built by Kishan as part of PhD research on ML reproducibility and data governance.

- GitHub: [@kishanraj41](https://github.com/yourusername)
- Email: kishanraj41@gmail.com

## Star History

If you find AutoLineage useful, please star the repository!

## Citation

If you use AutoLineage in your research, please cite:
```bibtex
@software{autolineage2025,
  author = Kishan Raj Vandhavasi Goutham Kumar,
  title = {AutoLineage: Automatic ML Data Lineage Tracking},
  year = {2025},
  url = {https://github.com/kishanraj41/autolineage}
}
```

## Roadmap

- [x] Automatic pandas/numpy tracking
- [x] Visual lineage graphs
- [x] CLI interface
- [x] EU AI Act compliance reports
- [x] Jupyter magic commands
- [ ] MLflow integration
- [ ] Git integration
- [ ] Column-level lineage
- [ ] Data drift detection
- [ ] Team collaboration features
- [ ] Cloud storage support

## FAQ

**Q: Does this slow down my code?**
A: Minimal overhead - just file I/O tracking. Typically <1% performance impact.

**Q: Do I need to change my code?**
A: No! Just `import autolineage.auto` at the top. Everything else is automatic.

**Q: What Python versions are supported?**
A: Python 3.8+

**Q: Can I use this in production?**
A: Yes! It's lightweight and has minimal dependencies.

**Q: How is this different from MLflow?**
A: AutoLineage focuses on automatic data lineage (zero manual logging), while MLflow is a complete MLOps platform. They complement each other!

---

**Made with ❤️ for the ML community**
```

**Save:** `Ctrl+S`

---

## **4.3: Create LICENSE File**

**Create file: `LICENSE`**
```
MIT License

Copyright (c) 2025 Kishan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Save:** `Ctrl+S`

---

## **4.4: Create .gitignore (if not exists)**

**Update: `.gitignore`**
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
pip-wheel-metadata/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environment
venv/
env/
ENV/
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Database
*.db
*.sqlite
*.sqlite3

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Documentation
docs/_build/
site/

# Jupyter
.ipynb_checkpoints/
*.ipynb_checkpoints

# Generated files
*.csv
*.parquet
*.json
*.png
*.html
*.md
!README.md
!docs/*.md
!LICENSE

# Logs
*.log
