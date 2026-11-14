import pandas as pd

rows = pd.DataFrame({
    "date": pd.to_datetime(["2020-08-04"] * 200),
    "source": ["lab_a"] * 100 + ["lab_b"] * 100,
})
published = rows.dropna()
