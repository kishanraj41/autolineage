import pandas as pd

states = pd.DataFrame({"state": ["NY", "NJ", "TX", "GA"], "deaths": [10, 11, 12, 13]})
priority = pd.DataFrame({"state": ["NY", "NJ"], "from_priority": [10, 11]})
merged = states.merge(priority, on="state", how="inner")  # fault
