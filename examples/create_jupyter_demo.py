"""
Create a demo Jupyter notebook for AutoLineage.
"""

import nbformat as nbf

# Create notebook
nb = nbf.v4.new_notebook()

# Add cells
cells = [
    # Title
    nbf.v4.new_markdown_cell("""# AutoLineage Jupyter Demo

This notebook demonstrates AutoLineage's automatic data lineage tracking in Jupyter.
"""),
    
    # Load extension
    nbf.v4.new_markdown_cell("## 1. Load AutoLineage Extension"),
    nbf.v4.new_code_cell("%load_ext autolineage"),
    
    # Start tracking
    nbf.v4.new_markdown_cell("## 2. Start Lineage Tracking"),
    nbf.v4.new_code_cell("%lineage_start"),
    
    # Create data
    nbf.v4.new_markdown_cell("## 3. Create and Process Data\n\nEverything is tracked automatically!"),
    nbf.v4.new_code_cell("""import pandas as pd
import numpy as np

# Create sample data
df = pd.DataFrame({
    'product': ['A', 'B', 'C', 'D', 'E'],
    'sales': [100, 150, 120, 200, 180],
    'profit': [20, 30, 25, 40, 35]
})

# Save to CSV
df.to_csv('notebook_sales.csv', index=False)
print("✓ Created sales data")"""),
    
    # Clean data
    nbf.v4.new_code_cell("""# Load and clean data
df_loaded = pd.read_csv('notebook_sales.csv')
df_clean = df_loaded[df_loaded['sales'] > 100]

# Save cleaned data
df_clean.to_csv('notebook_sales_clean.csv', index=False)
print(f"✓ Cleaned data: {len(df_clean)} rows")"""),
    
    # Aggregate
    nbf.v4.new_code_cell("""# Aggregate data
df_summary = pd.read_csv('notebook_sales_clean.csv')
summary = df_summary[['sales', 'profit']].describe()

# Save summary
summary.to_csv('notebook_summary.csv')
print("✓ Created summary")"""),
    
    # Show summary
    nbf.v4.new_markdown_cell("## 4. View Lineage Summary"),
    nbf.v4.new_code_cell("%lineage_summary"),
    
    # Visualize
    nbf.v4.new_markdown_cell("## 5. Visualize Lineage Graph\n\nInteractive graph showing data flow:"),
    nbf.v4.new_code_cell("%lineage_show --format html"),
    
    # Generate report
    nbf.v4.new_markdown_cell("## 6. Generate Compliance Report"),
    nbf.v4.new_code_cell("%lineage_report"),
    
    # Cell magic demo
    nbf.v4.new_markdown_cell("## 7. Cell Magic Demo\n\nTrack a specific cell:"),
    nbf.v4.new_code_cell("""%%lineage_track
# This cell is tracked automatically
df_test = pd.DataFrame({'x': [1, 2, 3]})
df_test.to_csv('test_cell_magic.csv', index=False)"""),
    
    # Stop tracking
    nbf.v4.new_markdown_cell("## 8. Stop Tracking"),
    nbf.v4.new_code_cell("%lineage_stop"),
    
    # Summary
    nbf.v4.new_markdown_cell("""## Summary

You've just seen:
- ✅ Automatic lineage tracking in Jupyter
- ✅ Visual lineage graphs
- ✅ Compliance report generation
- ✅ Cell-level tracking

All with zero manual logging! 🎉

**Next steps:**
- Try `%lineage_show --format png` for static images
- Use `%lineage_report --save report.md` to save reports
- Explore the generated `notebook_lineage.db` database
"""),
]

nb['cells'] = cells

# Write notebook
with open('jupyter_demo.ipynb', 'w', encoding='utf-8') as f:
    nbf.write(nb, f)

print("✅ Created jupyter_demo.ipynb")
print("\nTo use:")
print("  1. Install Jupyter: pip install jupyter notebook")
print("  2. Start Jupyter: jupyter notebook")
print("  3. Open: jupyter_demo.ipynb")
print("  4. Run all cells!")