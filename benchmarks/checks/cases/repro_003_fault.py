import pandas as pd

orders = pd.DataFrame({"order_id": range(1, 17), "customer_id": [1, 2, 3, 4] * 4, "amount": [100] * 16})
customers = pd.DataFrame({"customer_id": [1, 2, 2, 3, 4], "segment": ["a", "b", "b", "c", "d"]})
joined = orders.merge(customers, on="customer_id", how="left")  # fault
