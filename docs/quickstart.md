# Quickstart

The shortest path is the README: it opens with a one-import example, the install line, and a 30-second Colab notebook you can run without installing anything.

- README: https://github.com/kishanraj41/autolineage#readme
- Colab notebook: https://colab.research.google.com/github/kishanraj41/autolineage/blob/main/examples/quickstart.ipynb

## Install

```bash
pip install "autolineage[sklearn]"     # pandas + scikit-learn hooks
pip install "autolineage[all]"         # adds PySpark hooks and Jupyter extras
```

## One import

```python
import autolineage.auto                # must come before you import tracked symbols

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
# ... your pipeline, unchanged ...

from autolineage.auto import get_tracker
tracker = get_tracker()
print(tracker)                         # summary of recorded operations
tracker.visualize("trace.html")        # interactive graph, self-contained HTML
tracker.to_mermaid()                   # or Graphviz: tracker.to_dot()
```

`import autolineage.auto` patches pandas, scikit-learn and PySpark at import time. A symbol your script imports *before* that line (for example `from sklearn.metrics import f1_score`) is rebound to the tracked version automatically, with a warning; a symbol imported early inside another module is not, and bypasses the hook. Putting `import autolineage.auto` first avoids both.

## Catch a silent regression

```python
from autolineage.core.analyzer import LineageAnalyzer

# healthy run
analyzer = LineageAnalyzer(get_tracker())
analyzer.save_fingerprint("baseline.json")

# later run, fresh process
analyzer = LineageAnalyzer(get_tracker())
analyzer.load_baseline("baseline.json")
for a in analyzer.detect_anomalies():
    print(a.severity, a.message)
print(analyzer.localize_root_cause("f1_score").explanation)
```

## Runnable examples

- `examples/pipeline.py`: the 22-line script from the README recording; writes `trace.html`.
- `examples/anomaly_demo.py`: runs a pipeline clean, then with a planted filter bug, and localizes the bug. This is the hero GIF.
- `examples/quickstart.ipynb`: the Colab notebook.

## Not a CLI

Earlier versions (0.1 to 0.3) shipped a `lineage` command-line tool, a SQLite-backed `DatasetTracker` and an EU AI Act compliance reporter. Those were removed in v0.4.1 and are not coming back in that form; the library is a Python API only. If you need an exported artifact, `tracker.visualize("trace.html")` and `LineageAnalyzer.save_fingerprint()` write self-contained files.
