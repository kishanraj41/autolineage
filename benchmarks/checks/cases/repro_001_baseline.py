import pandas as pd

values = pd.Series(["2024-01-01"] * 10)
parsed = pd.to_datetime(values, errors="coerce")
