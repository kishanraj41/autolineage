"""
Real-World ML Pipeline Demo: California Housing Price Prediction

Demonstrates AutoLineage tracking a complete, realistic ML workflow:
  1. Data loading from CSV
  2. Exploratory cleaning (null handling, outlier removal)
  3. Feature engineering (new columns, binning, interactions)
  4. Train/test split
  5. Model training & evaluation
  6. Lineage report generation

All transformations are tracked automatically with zero manual logging.

Dataset: California Housing (20,640 samples, 10 features)
  Source: https://raw.githubusercontent.com/ageron/handson-ml2/master/datasets/housing/housing.csv
  Place the file at: examples/data/housing.csv

Task: Predict median house value

Usage:
    python examples/california_housing_pipeline.py
"""

import os
import sys
import json

# === STEP 0: Enable AutoLineage (one line) ===
import autolineage.auto

import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from autolineage.df_tracker import get_df_tracker


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(script_dir, 'data', 'housing.csv')
    output_dir = os.path.join(script_dir, '..', 'demo_output')
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(data_path):
        print(f"ERROR: Dataset not found at {data_path}")
        print(f"Download it from:")
        print(f"  https://raw.githubusercontent.com/ageron/handson-ml2/master/datasets/housing/housing.csv")
        print(f"Place it at: examples/data/housing.csv")
        sys.exit(1)

    print("=" * 60)
    print("  California Housing — AutoLineage Demo Pipeline")
    print("=" * 60)

    # ================================================================
    # STEP 1: Load raw data
    # ================================================================
    print("\n[1/7] Loading California Housing dataset...")
    df = pd.read_csv(data_path)
    print(f"       Shape: {df.shape[0]:,} rows x {df.shape[1]} columns")
    print(f"       Columns: {list(df.columns)}")
    print(f"       Nulls: {df.isnull().sum().to_dict()}")

    # Save a copy as our "raw" artifact
    raw_path = os.path.join(output_dir, '01_raw_data.csv')
    df.to_csv(raw_path, index=False)

    # ================================================================
    # STEP 2: Data cleaning
    # ================================================================
    print("\n[2/7] Cleaning data...")

    # 2a. Handle nulls in total_bedrooms (real nulls in this dataset)
    nulls_before = df['total_bedrooms'].isna().sum()
    df_clean = df.dropna(subset=['total_bedrooms'])
    print(f"       Dropped {nulls_before} rows with null total_bedrooms")
    print(f"       After dropna: {df_clean.shape[0]:,} rows")

    # 2b. Remove outliers
    df_clean = df_clean.query(
        'median_income < 15 and housing_median_age <= 52'
    )
    print(f"       After outlier removal: {df_clean.shape[0]:,} rows")

    # 2c. Remove extreme house values (capped at 500001 in original)
    df_clean = df_clean[df_clean['median_house_value'] < 500001]
    print(f"       After removing capped values: {df_clean.shape[0]:,} rows")

    # Save cleaned data
    clean_path = os.path.join(output_dir, '02_cleaned_data.csv')
    df_clean.to_csv(clean_path, index=False)

    # ================================================================
    # STEP 3: Feature engineering
    # ================================================================
    print("\n[3/7] Engineering features...")

    # 3a. Per-household ratios
    df_feat = df_clean.assign(
        rooms_per_household=lambda x: x['total_rooms'] / x['households'],
        bedrooms_per_room=lambda x: x['total_bedrooms'] / x['total_rooms'],
        population_per_household=lambda x: x['population'] / x['households'],
    )
    print(f"       Added per-household ratio features")

    # 3b. Log-transform skewed features
    df_feat = df_feat.assign(
        log_population=lambda x: np.log1p(x['population']),
        log_total_rooms=lambda x: np.log1p(x['total_rooms']),
        log_income=lambda x: np.log1p(x['median_income']),
    )
    print(f"       Added log-transformed features")

    # 3c. Geographic binning
    df_feat = df_feat.assign(
        lat_bin=pd.cut(
            df_feat['latitude'],
            bins=[32, 34, 36, 38, 40, 42],
            labels=['SoCal', 'Central_S', 'Central_N', 'NorCal_S', 'NorCal_N']
        ).astype(str)
    )
    print(f"       Added geographic bin feature")

    # 3d. Age categories
    df_feat = df_feat.assign(
        age_category=pd.cut(
            df_feat['housing_median_age'],
            bins=[0, 10, 20, 35, 52],
            labels=['new', 'recent', 'established', 'old']
        ).astype(str)
    )
    print(f"       Added age category feature")
    print(f"       Final feature set: {df_feat.shape[1]} columns")

    # Save engineered features
    feat_path = os.path.join(output_dir, '03_features.csv')
    df_feat.to_csv(feat_path, index=False)

    # ================================================================
    # STEP 4: Prepare train/test split
    # ================================================================
    print("\n[4/7] Splitting train/test...")

    target_col = 'median_house_value'
    feature_cols = [
        'longitude', 'latitude', 'housing_median_age', 'total_rooms',
        'total_bedrooms', 'population', 'households', 'median_income',
        'rooms_per_household', 'bedrooms_per_room', 'population_per_household',
        'log_population', 'log_total_rooms', 'log_income',
    ]

    X = df_feat[feature_cols]
    y = df_feat[[target_col]]

    # Use pandas boolean mask so lineage tracks the split
    np.random.seed(42)
    train_mask = pd.Series(np.random.random(len(X)) < 0.8, index=X.index)
    X_train = X[train_mask]
    X_test = X[~train_mask]
    y_train = y[train_mask]
    y_test = y[~train_mask]

    print(f"       Train: {len(X_train):,} samples")
    print(f"       Test:  {len(X_test):,} samples")

    # Save splits
    X_train.to_csv(os.path.join(output_dir, '04_X_train.csv'), index=False)
    X_test.to_csv(os.path.join(output_dir, '04_X_test.csv'), index=False)
    y_train.to_csv(os.path.join(output_dir, '04_y_train.csv'), index=False)
    y_test.to_csv(os.path.join(output_dir, '04_y_test.csv'), index=False)

    # ================================================================
    # STEP 5: Train model
    # ================================================================
    print("\n[5/7] Training GradientBoostingRegressor...")

    model = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        random_state=42,
    )
    model.fit(X_train.values, y_train.values.ravel())
    print(f"       Model trained with {model.n_estimators} estimators")

    # Save model with joblib (tracked by AutoLineage)
    import joblib
    model_path = os.path.join(output_dir, '05_model.joblib')
    joblib.dump(model, model_path)
    print(f"       Model saved")

    # ================================================================
    # STEP 6: Evaluate
    # ================================================================
    print("\n[6/7] Evaluating model...")

    y_pred = model.predict(X_test.values)
    predictions = X_test.assign(
        actual=y_test.values.ravel(),
        predicted=y_pred,
        residual=y_test.values.ravel() - y_pred,
        abs_error=np.abs(y_test.values.ravel() - y_pred),
    )

    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print(f"       RMSE:  ${rmse:,.0f}")
    print(f"       MAE:   ${mae:,.0f}")
    print(f"       R²:    {r2:.4f}")

    # Save predictions and metrics
    pred_path = os.path.join(output_dir, '06_predictions.csv')
    predictions.to_csv(pred_path, index=False)

    metrics = {
        'rmse': round(float(rmse), 2),
        'mae': round(float(mae), 2),
        'r2': round(float(r2), 4),
        'n_train': len(X_train),
        'n_test': len(X_test),
        'n_features': len(feature_cols),
        'model': 'GradientBoostingRegressor',
        'n_estimators': 200,
    }
    metrics_path = os.path.join(output_dir, '06_metrics.json')
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)

    # ================================================================
    # STEP 7: AutoLineage Report
    # ================================================================
    print("\n[7/7] Generating lineage report...")

    dt = get_df_tracker()
    summary = dt.get_summary()

    print(f"\n{'='*60}")
    print(f"  AUTOLINEAGE TRACKING SUMMARY")
    print(f"{'='*60}")
    print(f"  DataFrames tracked:    {summary['total_dataframes']}")
    print(f"  Transformations:       {summary['total_transformations']}")
    print(f"  Rows filtered:         {summary['total_rows_filtered']:,}")
    print(f"  Column changes:        {summary['total_column_changes']}")
    print(f"\n  Operations breakdown:")
    for op, count in sorted(summary['operation_counts'].items(), key=lambda x: -x[1]):
        print(f"    {op:<25} {count:>3}x")

    # Full transformation chain
    print(f"\n{'='*60}")
    print(f"  COMPLETE DATA LINEAGE")
    print(f"{'='*60}")
    for i, t in enumerate(dt.transformations):
        shape_str = ""
        if t.input_shape and t.output_shape:
            shape_str = f" [{t.input_shape} → {t.output_shape}]"
        elif t.output_shape:
            shape_str = f" [→ {t.output_shape}]"

        detail = ""
        if t.rows_before is not None and t.rows_after is not None and t.rows_before != t.rows_after:
            detail += f" rows:{t.rows_before}→{t.rows_after}"
        if t.columns_added:
            detail += f" +cols:{t.columns_added}"
        if t.columns_removed:
            detail += f" -cols:{t.columns_removed}"

        print(f"  {i+1:>3}. {t.operation:<25}{shape_str}{detail}")

    # File mappings
    print(f"\n  File → DataFrame mappings:")
    for filepath, node_id in dt._file_to_node.items():
        print(f"    {os.path.basename(filepath):<35} → {node_id}")

    # Save lineage as JSON
    lineage_path = os.path.join(output_dir, '07_lineage.json')
    graph = dt.get_full_graph()
    with open(lineage_path, 'w') as f:
        json.dump(graph, f, indent=2, default=str)
    print(f"\n  Full lineage graph saved to: {lineage_path}")

    # Summary of all output files
    print(f"\n{'='*60}")
    print(f"  OUTPUT FILES")
    print(f"{'='*60}")
    for fname in sorted(os.listdir(output_dir)):
        fsize = os.path.getsize(os.path.join(output_dir, fname))
        print(f"    {fname:<35} {fsize:>10,} bytes")


if __name__ == '__main__':
    main()
