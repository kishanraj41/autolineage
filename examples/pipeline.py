import autolineage.auto                       # 1. one import; tracking is on

import pandas as pd
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score

df = load_breast_cancer(as_frame=True).frame  # 2. your normal pandas + sklearn code
df = df.dropna()
df = df[df["mean radius"] < 25]

X, y = df.drop(columns=["target"]), df["target"]
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=0)
model = RandomForestClassifier(n_estimators=100, random_state=0).fit(X_tr, y_tr)
print("F1 =", round(f1_score(y_te, model.predict(X_te)), 4))

from autolineage.auto import get_tracker      # 3. see what was captured
tracker = get_tracker()
print(tracker)
tracker.visualize("trace.html", open_browser=False)
print("wrote trace.html  (open it in a browser)")
