# Jupyter Magic Demo

Copy these commands into a Jupyter notebook to test:
```python
# Load extension
%load_ext autolineage

# Start tracking
%lineage_start

# Your data science code
import pandas as pd

df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
df.to_csv('test.csv', index=False)

df2 = pd.read_csv('test.csv')
df3 = df2[df2['a'] > 1]
df3.to_csv('filtered.csv', index=False)

# View summary
%lineage_summary

# Show graph
%lineage_show

# Generate report
%lineage_report

# Stop tracking
%lineage_stop
```

## Cell Magic Example
```python
%%lineage_track
# This entire cell is tracked
df = pd.read_csv('data.csv')
df_processed = df.dropna()
df_processed.to_csv('output.csv')
```