# CLI Reference

Complete guide to AutoLineage command-line interface.

## Installation
```bash
pip install autolineage
```

The `lineage` command will be available globally.

## Commands

### `lineage track`

Track lineage for a Python script.
```bash
lineage track SCRIPT_PATH [OPTIONS]
```

**Arguments:**
- `SCRIPT_PATH`: Path to Python script to track

**Options:**
- `--db PATH`: Database path (default: lineage.db)

**Example:**
```bash
lineage track my_pipeline.py
lineage track train_model.py --db experiment_001.db
```

---

### `lineage show`

Visualize the lineage graph.
```bash
lineage show [OPTIONS]
```

**Options:**
- `--db PATH`: Database path (default: lineage.db)
- `--output, -o PATH`: Output file path
- `--format [png|html]`: Output format (default: png)

**Examples:**
```bash
# Static PNG image
lineage show --output graph.png

# Interactive HTML
lineage show --format html --output graph.html

# From specific database
lineage show --db experiment.db --format html
```

---

### `lineage summary`

Show lineage summary statistics.
```bash
lineage summary [OPTIONS]
```

**Options:**
- `--db PATH`: Database path (default: lineage.db)

**Example:**
```bash
lineage summary
lineage summary --db my_experiment.db
```

---

### `lineage report`

Generate EU AI Act compliance report.
```bash
lineage report [OPTIONS]
```

**Options:**
- `--db PATH`: Database path (default: lineage.db)
- `--format [markdown|json|both]`: Report format (default: markdown)
- `--output, -o PATH`: Output file path

**Examples:**
```bash
# Markdown report
lineage report --format markdown

# JSON report
lineage report --format json --output compliance.json

# Both formats
lineage report --format both

# Custom output path
lineage report --output my_report.md
```

---

### `lineage clear`

Delete the lineage database.
```bash
lineage clear [OPTIONS]
```

**Options:**
- `--db PATH`: Database path (default: lineage.db)

**Example:**
```bash
lineage clear
lineage clear --db old_experiment.db
```

**Note:** This will prompt for confirmation before deleting.

---

## Complete Workflow Example
```bash
# 1. Track your pipeline
lineage track train_model.py

# 2. View what was tracked
lineage summary

# 3. Generate visualizations
lineage show --format html --output lineage.html

# 4. Generate compliance report
lineage report --format both

# 5. Clean up when done
lineage clear
```

## Tips

1. **Database Management**: Use `--db` to keep different experiments separate
```bash
   lineage track exp1.py --db exp1.db
   lineage track exp2.py --db exp2.db
```

2. **HTML Graphs**: Interactive HTML graphs are great for presentations
```bash
   lineage show --format html --output presentation.html
```

3. **Automated Reporting**: Integrate into CI/CD pipelines
```bash
   lineage track pipeline.py && lineage report --format json
```