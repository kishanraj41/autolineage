import pandas as pd

values = pd.Series(["2024-01-01"] * 8 + ["not-a-date", "also-bad"])
parsed = pd.to_datetime(values, errors="coerce")  # fault
