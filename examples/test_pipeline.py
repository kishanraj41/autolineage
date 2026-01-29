"""
Simple test pipeline for CLI tracking.
"""

import pandas as pd

# Create data
df = pd.DataFrame({
    'product': ['A', 'B', 'C'],
    'sales': [100, 200, 150]
})
df.to_csv('products.csv', index=False)

# Process
df = pd.read_csv('products.csv')
df_filtered = df[df['sales'] > 100]
df_filtered.to_csv('high_sales.csv', index=False)

print("✓ Pipeline completed!")