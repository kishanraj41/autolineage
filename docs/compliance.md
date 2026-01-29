# EU AI Act Compliance

AutoLineage generates compliance reports for EU AI Act Article 10 (Data and Data Governance).

## What is EU AI Act Article 10?

Article 10 of the EU Artificial Intelligence Act requires:

1. **High-quality training data**: Appropriate, relevant, and representative
2. **Data governance**: Examination of biases, gaps, and shortcomings
3. **Processing operations**: Documentation of all data transformations
4. **Traceability**: Complete lineage from source to model

## Generating Compliance Reports

### Via CLI
```bash
# Generate markdown report
lineage report --format markdown

# Generate JSON report (machine-readable)
lineage report --format json

# Generate both
lineage report --format both
```

### Via Python API
```python
from autolineage import DatasetTracker, ComplianceReporter

tracker = DatasetTracker('lineage.db')
reporter = ComplianceReporter(tracker.db)

# Generate markdown
reporter.save_markdown('compliance_report.md')

# Generate JSON
reporter.save_json('compliance_report.json')

tracker.close()
```

### Via Jupyter
```python
%load_ext autolineage
%lineage_start

# ... your data science code ...

# Generate report
%lineage_report --save compliance.md
```

## What's Included in the Report

The compliance report includes:

1. **Executive Summary**
   - Total datasets tracked
   - Data transformations count
   - Lineage relationships
   - Compliance status

2. **Data Sources Inventory**
   - Complete list of all datasets
   - SHA-256 hashes for verification
   - File sizes and formats
   - Creation timestamps

3. **Data Transformations**
   - All processing operations
   - Code references
   - Parameters used
   - Execution timestamps

4. **Lineage Graph**
   - Complete data flow visualization
   - Source to output chain
   - Transformation operations

5. **Compliance Statement**
   - Mapping to Article 10 requirements
   - Regulatory declarations
   - Verification methods

6. **Verification Instructions**
   - Hash verification commands
   - Reproducibility guidelines
   - Audit trail access

## Example Report Structure
```markdown
# ML Model Data Lineage Report

**Report Type:** EU AI Act Article 10 Compliance
**Generated:** 2025-01-29 12:00:00 UTC
**Standard:** EU Artificial Intelligence Act

## Executive Summary
- Total Datasets: 5
- Data Transformations: 3
- Compliance Status: COMPLIANT

## 1. Data Sources
#### Dataset 1: training_data.csv
- SHA-256: abc123...
- Size: 1.2 MB
- Verified

[... more details ...]
```

## Verification

To verify data integrity:
```bash
# Linux/Mac
sha256sum training_data.csv

# Windows
certutil -hashfile training_data.csv SHA256
```

Compare the output with the hash in the compliance report.

## Best Practices

1. **Track Everything**: Use `autolineage.auto` to ensure complete tracking
2. **Generate Reports Regularly**: Create reports after each training run
3. **Archive Reports**: Store reports with model checkpoints
4. **Version Control**: Keep reports in git alongside code
5. **Automate**: Integrate into CI/CD pipelines

## Integration with Model Registry
```python
# Example: Save report with model
from autolineage import ComplianceReporter

reporter = ComplianceReporter(db)
report_json = reporter.generate_json()

# Save with your model
model_metadata = {
    'model': model,
    'metrics': metrics,
    'lineage_report': report_json  # Include compliance data
}
```

## Questions?

- See [examples/compliance_report_test.py](../examples/compliance_report_test.py)
- Check the generated `compliance_report.md` sample
- Review EU AI Act text: [EUR-Lex](https://eur-lex.europa.eu/)