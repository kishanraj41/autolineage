"""NOTE: reproduces the mechanism with synthetic data, not the original data or exact figures.
Merge fan-out: a left join on a key that is not unique on the right.

Pattern behind SF-018/SF-022/SF-031 and the most common silent failure in
practice: rows multiply, sums inflate, nothing raises. `validate="one_to_one"`
or `"many_to_one"` is the one-line fix; almost nobody writes it.
Run: python repro_003_merge_fanout.py
"""
import pandas as pd

orders = pd.DataFrame({"order_id": range(1, 17), "customer_id": [1, 2, 3, 4] * 4, "amount": [100] * 16})
# A customer dimension that accidentally has two rows for customer 2 (a reload
# appended instead of replacing).
customers = pd.DataFrame({"customer_id": [1, 2, 2, 3, 4], "segment": ["a", "b", "b", "c", "d"]})

joined = orders.merge(customers, on="customer_id", how="left")
print(f"orders in: {len(orders)}  rows out: {len(joined)}  revenue in: {orders.amount.sum()}  revenue out: {joined.amount.sum()}")
print("no exception was raised")

# The check: rows_out must equal rows_in for a left join; or declare it.
try:
    orders.merge(customers, on="customer_id", how="left", validate="many_to_one")
except pd.errors.MergeError as e:
    print("with validate='many_to_one':", type(e).__name__)
