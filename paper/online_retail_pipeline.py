"""
Pipeline 3: UCI Online Retail — Customer Churn & RFM Analysis
=============================================================
Real transactional data from a UK-based online retailer.
541,909 invoices, Dec 2010 – Dec 2011.

Dataset: Chen, D. (2015). Online Retail [Dataset].
         UCI Machine Learning Repository.
         https://doi.org/10.24432/C5BW33
License: CC BY 4.0

Setup:
    pip install ucimlrepo
    python paper/online_retail_pipeline.py

Or download manually:
    https://archive.ics.uci.edu/dataset/352/online+retail
    Place "Online Retail.xlsx" in paper/data/

This pipeline demonstrates AutoLineage on a REAL, MESSY dataset:
  - 541K rows with 135K missing CustomerIDs
  - Cancellations (negative quantities) mixed in
  - Multi-step cleaning with data-dependent thresholds
  - GroupBy aggregations to build customer-level features
  - RFM (Recency-Frequency-Monetary) scoring
  - Time-based feature engineering
  - Churn labeling from transaction recency
  - 30+ tracked transformations
"""

import os
import sys
import json
import time
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import autolineage.auto
from autolineage.df_tracker import get_df_tracker


def load_data(data_dir):
    """Load UCI Online Retail dataset. Tries ucimlrepo first, then local file."""
    
    local_path = os.path.join(data_dir, 'Online Retail.xlsx')
    csv_path = os.path.join(data_dir, 'online_retail.csv')
    
    # Try local CSV first (fastest)
    if os.path.exists(csv_path):
        print("        Loading from local CSV...")
        return pd.read_csv(csv_path, parse_dates=['InvoiceDate'])
    
    # Try local Excel
    if os.path.exists(local_path):
        print("        Loading from local Excel...")
        df = pd.read_excel(local_path)
        # Save as CSV for faster reloads
        df.to_csv(csv_path, index=False)
        return df
    
    # Try ucimlrepo
    try:
        from ucimlrepo import fetch_ucirepo
        print("        Fetching from UCI ML Repository...")
        dataset = fetch_ucirepo(id=352)
        df = dataset.data.features
        # Combine with targets AND ids (InvoiceNo, StockCode are in ids)
        if dataset.data.targets is not None:
            df = pd.concat([df, dataset.data.targets], axis=1)
        if dataset.data.ids is not None:
            df = pd.concat([df, dataset.data.ids], axis=1)
            # Save locally
        os.makedirs(data_dir, exist_ok=True)
        df.to_csv(csv_path, index=False)
        print(f"        Saved to {csv_path} for future runs")
        return df
    except Exception as e:
        print(f"        ucimlrepo failed: {e}")
    
    print("\n  ERROR: Could not load data. Please either:")
    print("    1. pip install ucimlrepo")
    print("    2. Or download 'Online Retail.xlsx' from:")
    print("       https://archive.ics.uci.edu/dataset/352/online+retail")
    print(f"       and place it in: {data_dir}")
    sys.exit(1)


def rfm_segment(row):
    """Assign RFM segment label based on scores. Opaque to lineage (custom apply)."""
    r, f, m = row['R_Score'], row['F_Score'], row['M_Score']
    total = r + f + m
    
    if total >= 12:
        return 'Champions'
    elif total >= 9:
        return 'Loyal'
    elif r >= 4 and total >= 7:
        return 'Recent_High'
    elif r <= 2 and f >= 3:
        return 'At_Risk'
    elif r <= 2 and total <= 6:
        return 'Lost'
    elif r >= 3 and f <= 2:
        return 'New'
    else:
        return 'Regular'


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, 'data')
    output_dir = os.path.join(script_dir, 'retail_output')
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    print("=" * 70)
    print("  Pipeline 3: UCI Online Retail — Real-World Churn Analysis")
    print("  Dataset: 541K transactions, UK retailer, Dec 2010–Dec 2011")
    print("=" * 70)
    
    t_start = time.time()
    
    # === 1. Load ===
    print("\n[1/10] Loading UCI Online Retail dataset...")
    df = load_data(data_dir)
    print(f"        Raw data: {df.shape}")
    print(f"        Columns: {list(df.columns)}")
    print(f"        Null counts:\n{df.isnull().sum().to_string()}")
    
    # === 2. Initial cleaning ===
    print("\n[2/10] Cleaning raw transactions...")
    
    # Drop rows with missing CustomerID (135K rows — major real-world messiness)
    n_before = len(df)
    df_clean = df.dropna(subset=['CustomerID'])
    print(f"        Dropped null CustomerID: {n_before:,} → {len(df_clean):,} ({n_before - len(df_clean):,} removed)")
    
    # Remove cancellations (InvoiceNo starts with 'C')
    n_before = len(df_clean)
    df_clean = df_clean[~df_clean['InvoiceNo'].astype(str).str.startswith('C')]
    print(f"        Removed cancellations: {n_before:,} → {len(df_clean):,} ({n_before - len(df_clean):,} removed)")
    
    # Remove zero/negative prices
    n_before = len(df_clean)
    df_clean = df_clean[df_clean['UnitPrice'] > 0]
    print(f"        Removed zero prices: {n_before:,} → {len(df_clean):,}")
    
    # Remove zero/negative quantities
    n_before = len(df_clean)
    df_clean = df_clean[df_clean['Quantity'] > 0]
    print(f"        Removed zero quantities: {n_before:,} → {len(df_clean):,}")
    
    # === 3. Feature engineering on transactions ===
    print("\n[3/10] Engineering transaction-level features...")
    
    # Ensure datetime
    df_clean = df_clean.assign(
        InvoiceDate=pd.to_datetime(df_clean['InvoiceDate']),
    )
    
    # Revenue per line item
    df_clean = df_clean.assign(
        Revenue=lambda x: x['Quantity'] * x['UnitPrice'],
    )
    print(f"        Added Revenue column: {df_clean.shape}")
    
    # Time features
    df_clean = df_clean.assign(
        InvoiceMonth=lambda x: x['InvoiceDate'].dt.to_period('M').astype(str),
        InvoiceHour=lambda x: x['InvoiceDate'].dt.hour,
        InvoiceDayOfWeek=lambda x: x['InvoiceDate'].dt.dayofweek,
        IsWeekend=lambda x: (x['InvoiceDate'].dt.dayofweek >= 5).astype(int),
    )
    print(f"        Added time features: {df_clean.shape}")
    
    # === 4. Remove outliers (data-dependent thresholds) ===
    print("\n[4/10] Removing outliers...")
    
    q99_qty = df_clean['Quantity'].quantile(0.99)
    q99_price = df_clean['UnitPrice'].quantile(0.99)
    q99_rev = df_clean['Revenue'].quantile(0.99)
    print(f"        Thresholds: Qty>{q99_qty:.0f}, Price>{q99_price:.2f}, Revenue>{q99_rev:.2f}")
    
    n_before = len(df_clean)
    df_clean = df_clean[df_clean['Quantity'] <= q99_qty]
    df_clean = df_clean[df_clean['UnitPrice'] <= q99_price]
    df_clean = df_clean[df_clean['Revenue'] <= q99_rev]
    print(f"        After outlier removal: {n_before:,} → {len(df_clean):,}")
    
    # Save cleaned transactions
    df_clean.to_csv(os.path.join(output_dir, 'transactions_clean.csv'), index=False)
    
    # === 5. Customer-level aggregation (GroupBy) ===
    print("\n[5/10] Building customer-level features via GroupBy...")
    
    reference_date = df_clean['InvoiceDate'].max() + pd.Timedelta(days=1)
    print(f"        Reference date: {reference_date}")
    
    customer_agg = df_clean.groupby('CustomerID').agg(
        Recency=('InvoiceDate', lambda x: (reference_date - x.max()).days),
        Frequency=('InvoiceNo', 'nunique'),
        Monetary=('Revenue', 'sum'),
        AvgOrderValue=('Revenue', 'mean'),
        TotalQuantity=('Quantity', 'sum'),
        UniqueProducts=('StockCode', 'nunique'),
        AvgUnitPrice=('UnitPrice', 'mean'),
        TotalInvoices=('InvoiceNo', 'nunique'),
    ).reset_index()
    print(f"        Customer features: {customer_agg.shape}")
    
    # === 6. Order-level stats ===
    print("\n[6/10] Computing order-level statistics...")
    
    order_stats = df_clean.groupby(['CustomerID', 'InvoiceNo']).agg(
        OrderRevenue=('Revenue', 'sum'),
        OrderItems=('Quantity', 'sum'),
        OrderUniqueItems=('StockCode', 'nunique'),
    ).reset_index()
    print(f"        Order-level data: {order_stats.shape}")
    
    # Aggregate to customer level
    order_customer = order_stats.groupby('CustomerID').agg(
        MaxOrderValue=('OrderRevenue', 'max'),
        MinOrderValue=('OrderRevenue', 'min'),
        StdOrderValue=('OrderRevenue', 'std'),
        AvgItemsPerOrder=('OrderItems', 'mean'),
        MaxItemsPerOrder=('OrderItems', 'max'),
    ).reset_index()
    print(f"        Order stats per customer: {order_customer.shape}")
    
    order_customer = order_customer.fillna({'StdOrderValue': 0})
    
    # === 7. Time-based features ===
    print("\n[7/10] Building time-based features...")
    
    # Monthly purchase counts
    monthly = df_clean.groupby(['CustomerID', 'InvoiceMonth']).agg(
        MonthRevenue=('Revenue', 'sum'),
        MonthOrders=('InvoiceNo', 'nunique'),
    ).reset_index()
    print(f"        Monthly data: {monthly.shape}")
    
    # Active months and purchase consistency
    time_features = monthly.groupby('CustomerID').agg(
        ActiveMonths=('InvoiceMonth', 'nunique'),
        AvgMonthlyRevenue=('MonthRevenue', 'mean'),
        StdMonthlyRevenue=('MonthRevenue', 'std'),
        AvgMonthlyOrders=('MonthOrders', 'mean'),
    ).reset_index()
    print(f"        Time features: {time_features.shape}")
    
    time_features = time_features.fillna({'StdMonthlyRevenue': 0})
    
    # === 8. Country features ===
    print("\n[8/10] Building geographic features...")
    
    country_mode = df_clean.groupby('CustomerID')['Country'].agg(
        lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else 'Unknown'
    ).reset_index(name='Country')
    print(f"        Country per customer: {country_mode.shape}")
    
    country_mode = country_mode.assign(
        IsUK=lambda x: (x['Country'] == 'United Kingdom').astype(int)
    )
    
    # === 9. Merge all features and create target ===
    print("\n[9/10] Merging all feature tables...")
    
    # Start with customer aggregation
    df_final = customer_agg.merge(order_customer, on='CustomerID', how='left')
    print(f"        + order stats: {df_final.shape}")
    
    df_final = df_final.merge(time_features, on='CustomerID', how='left')
    print(f"        + time features: {df_final.shape}")
    
    df_final = df_final.merge(country_mode, on='CustomerID', how='left')
    print(f"        + country: {df_final.shape}")
    
    # RFM scoring
    df_final = df_final.assign(
        R_Score=pd.qcut(df_final['Recency'], 5, labels=[5,4,3,2,1]).astype(int),
        F_Score=pd.qcut(df_final['Frequency'].rank(method='first'), 5, labels=[1,2,3,4,5]).astype(int),
        M_Score=pd.qcut(df_final['Monetary'].rank(method='first'), 5, labels=[1,2,3,4,5]).astype(int),
    )
    print(f"        Added RFM scores: {df_final.shape}")
    
    df_final = df_final.assign(
        RFM_Total=lambda x: x['R_Score'] + x['F_Score'] + x['M_Score']
    )
    
    # Custom RFM segmentation (opaque apply)
    df_final = df_final.assign(
        RFM_Segment=df_final.apply(rfm_segment, axis=1)
    )
    print(f"        Added RFM segment (custom apply): {df_final.shape}")
    
    # Churn label: customers with Recency > 90 days = churned
    df_final = df_final.assign(
        Churned=(df_final['Recency'] > 90).astype(int)
    )
    churn_rate = df_final['Churned'].mean()
    print(f"        Churn rate: {churn_rate:.1%}")
    
    # Log transforms
    for col in ['Monetary', 'AvgOrderValue', 'TotalQuantity', 'Recency']:
        df_final = df_final.assign(**{f'Log_{col}': np.log1p(df_final[col])})
    print(f"        Added log transforms: {df_final.shape}")
    
    # Derived ratios
    df_final = df_final.assign(
        RevenuePerProduct=lambda x: x['Monetary'] / x['UniqueProducts'].clip(1),
        OrderConsistency=lambda x: 1 - (x['StdMonthlyRevenue'] / x['AvgMonthlyRevenue'].clip(0.01)).clip(0, 1),
    )
    print(f"        Added derived ratios: {df_final.shape}")
    
    # Save complete feature set
    df_final.to_csv(os.path.join(output_dir, 'customer_features.csv'), index=False)
    
    # === 10. Prepare model data ===
    print("\n[10/10] Preparing model-ready data...")
    
    # Drop non-numeric / ID columns
    drop_cols = ['CustomerID', 'Country', 'RFM_Segment']
    df_model = df_final.drop(columns=drop_cols)
    print(f"        Dropped IDs/categoricals: {df_model.shape}")
    
    y = df_model[['Churned']]
    X = df_model.drop(columns=['Churned'])
    print(f"        X: {X.shape}, y: {y.shape}")
    
    # Train/test split
    np.random.seed(42)
    mask = pd.Series(np.random.random(len(X)) < 0.8, index=X.index)
    X_train = X[mask]
    X_test = X[~mask]
    y_train = y[mask]
    y_test = y[~mask]
    print(f"        Train: {X_train.shape}, Test: {X_test.shape}")
    print(f"        Churn rate — train: {y_train['Churned'].mean():.3f}, test: {y_test['Churned'].mean():.3f}")
    
    # Save
    X_train.to_csv(os.path.join(output_dir, 'X_train.csv'), index=False)
    X_test.to_csv(os.path.join(output_dir, 'X_test.csv'), index=False)
    
    # === Lineage Report ===
    dt = get_df_tracker()
    summary = dt.get_summary()
    elapsed = time.time() - t_start
    
    print(f"\n{'='*70}")
    print(f"  AUTOLINEAGE TRACKING SUMMARY")
    print(f"{'='*70}")
    print(f"  Pipeline execution time:   {elapsed:.1f}s")
    print(f"  DataFrames tracked:        {summary['total_dataframes']}")
    print(f"  Transformations:           {summary['total_transformations']}")
    print(f"  Rows filtered:             {summary['total_rows_filtered']:,}")
    print(f"  Column changes:            {summary['total_column_changes']}")
    
    print(f"\n  Operations breakdown:")
    for op, count in sorted(summary['operation_counts'].items(), key=lambda x: -x[1]):
        print(f"    {op:<30} {count:>3}x")
    
    print(f"\n  Transformation chain (first 25):")
    for i, t in enumerate(dt.transformations[:25]):
        shape_str = ""
        if t.input_shape and t.output_shape:
            shape_str = f" [{t.input_shape} → {t.output_shape}]"
        detail = ""
        if t.rows_before is not None and t.rows_after is not None and t.rows_before != t.rows_after:
            detail += f" Δrows:{t.rows_after - t.rows_before:+,}"
        if t.columns_added:
            detail += f" +{len(t.columns_added)}cols"
        print(f"    {i+1:>3}. {t.operation:<25}{shape_str}{detail}")
    
    remaining = len(dt.transformations) - 25
    if remaining > 0:
        print(f"    ... and {remaining} more transformations")
    
    # Save lineage
    graph = dt.get_full_graph()
    with open(os.path.join(output_dir, 'lineage.json'), 'w') as f:
        json.dump(graph, f, indent=2, default=str)
    
    # Paper summary
    paper_summary = {
        'pipeline': 'UCI Online Retail — Customer Churn & RFM',
        'dataset': 'Chen, D. (2015). Online Retail. UCI ML Repository.',
        'dataset_url': 'https://doi.org/10.24432/C5BW33',
        'license': 'CC BY 4.0',
        'raw_rows': 541909,
        'raw_columns': 8,
        'null_customer_ids': 135080,
        'cancellations_removed': True,
        'final_customers': len(df_final),
        'final_features': X.shape[1],
        'churn_rate': round(churn_rate, 4),
        'transformations_tracked': summary['total_transformations'],
        'dataframes_tracked': summary['total_dataframes'],
        'rows_filtered': summary['total_rows_filtered'],
        'column_changes': summary['total_column_changes'],
        'operation_counts': summary['operation_counts'],
        'unique_operations': len(summary['operation_counts']),
        'execution_time_s': round(elapsed, 1),
    }
    with open(os.path.join(output_dir, 'pipeline_summary.json'), 'w') as f:
        json.dump(paper_summary, f, indent=2)
    
    print(f"\n{'='*70}")
    print(f"  KEY METRICS FOR PAPER:")
    print(f"    Dataset:            UCI Online Retail (Chen, 2015)")
    print(f"    Raw transactions:   541,909")
    print(f"    Missing CustomerID: 135,080 (real-world messiness)")
    print(f"    Final customers:    {len(df_final):,}")
    print(f"    Final features:     {X.shape[1]}")
    print(f"    Transformations:    {summary['total_transformations']}")
    print(f"    Unique op types:    {len(summary['operation_counts'])}")
    print(f"    Execution time:     {elapsed:.1f}s")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
