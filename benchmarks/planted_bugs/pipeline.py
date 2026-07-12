import sys, json
CASE = sys.argv[1]; MODE = sys.argv[2]; buggy = (MODE=="buggy")
import autolineage.auto
from autolineage.auto import get_tracker
from autolineage.core.analyzer import LineageAnalyzer
import pandas as pd, numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, accuracy_score

def make_data(seed=0, n=6000):
    rng = np.random.default_rng(seed)
    amount = rng.exponential(50, n)
    region = rng.choice(["north","south","east","west"], n)
    y = ((amount > np.quantile(amount,0.80)) ^ (rng.random(n) < 0.05)).astype(int)
    return pd.DataFrame({"amount": amount, "region": region, "y": y})

def fit_score(df):
    d = df.copy()
    cat = [c for c in ["region","tier"] if c in d.columns]
    X = pd.get_dummies(d.drop(columns=["y"]), columns=cat, drop_first=True, dtype=float)
    X = X.drop(columns=[c for c in X.columns if X[c].dtype==object])
    y = d["y"]
    Xtr,Xte,ytr,yte = train_test_split(X, y, test_size=0.3, random_state=0)
    sc = StandardScaler(); Xtr = sc.fit_transform(Xtr); Xte = sc.transform(Xte)
    m = LogisticRegression(max_iter=200).fit(Xtr, ytr); p = m.predict(Xte)
    return f1_score(yte,p,zero_division=0), accuracy_score(yte,p)

def build(case, buggy):
    df = make_data()
    if case == "filter":
        df = df[df["amount"] <= df["amount"].quantile(0.05 if buggy else 0.999)]
        return fit_score(df)
    if case == "join":
        df["tier"] = np.where(df["amount"] > df["amount"].median(), "A", "B")
        lut = pd.DataFrame({"region":["north","south","east","west"]*2,
                            "tier":["A","A","A","A","B","B","B","B"], "fee":[1,2,3,4,5,6,7,8]})
        df = df.merge(lut, on=(["region"] if buggy else ["region","tier"]), how="left")
        return fit_score(df)
    if case == "encoding":
        df["customer_id"] = (np.arange(len(df)) % 400).astype(str)
        df = pd.get_dummies(df, columns=(["customer_id"] if buggy else ["region"]), drop_first=True, dtype=float)
        df = df.drop(columns=[c for c in df.columns if df[c].dtype==object])
        y=df["y"]; X=df.drop(columns=["y"])
        Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=0.3,random_state=0)
        sc=StandardScaler(); Xtr=sc.fit_transform(Xtr); Xte=sc.transform(Xte)
        m=LogisticRegression(max_iter=200).fit(Xtr,ytr); p=m.predict(Xte)
        return f1_score(yte,p,zero_division=0), accuracy_score(yte,p)
    if case == "leakage":
        base = df if buggy else df.drop(columns=["y"])   # buggy leaves target y in the features
        X = pd.get_dummies(base, columns=["region"], drop_first=True, dtype=float)
        X = X.drop(columns=[c for c in X.columns if X[c].dtype==object])
        y = df["y"]
        Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=0.3,random_state=0)
        sc=StandardScaler(); Xtr=sc.fit_transform(Xtr); Xte=sc.transform(Xte)
        m=LogisticRegression(max_iter=200).fit(Xtr,ytr); p=m.predict(Xte)
        return f1_score(yte,p,zero_division=0), accuracy_score(yte,p)
    if case == "type":
        df["code"] = df["amount"].round().astype(int).astype(str)
        if buggy:
            df.loc[df.sample(frac=0.4, random_state=1).index, "code"] = "N/A"
        df["code"] = pd.to_numeric(df["code"], errors="coerce")
        df = df.dropna(subset=["code"])
        return fit_score(df)

EXPECT = {"filter":"filter","join":"merge","encoding":"StandardScaler.fit_transform",
          "leakage":"StandardScaler.fit_transform","type":"dropna"}
f1, acc = build(CASE, buggy)
tr = get_tracker(); an = LineageAnalyzer(tr); fp = f"/tmp/exp/fp_{CASE}.json"
if MODE=="baseline":
    an.save_fingerprint(fp)
    print(json.dumps({"case":CASE,"base_f1":round(f1,4),"base_acc":round(acc,4)}))
else:
    an.load_baseline(fp); anoms = an.detect_anomalies()
    top = [{"op":a.operation,"metric":a.metric,"sev":a.severity,"dev":round(float(a.deviation),1)} for a in anoms]
    rc=None
    for metric in ["f1_score","accuracy_score"]:
        try:
            r=an.localize_root_cause(metric)
            if r: rc={"metric":metric,"root_op":r.root_operation,"impact":round(float(r.impact_score),2)}; break
        except Exception as e: rc={"error":repr(e)[:80]}
    print(json.dumps({"case":CASE,"buggy_f1":round(f1,4),"buggy_acc":round(acc,4),
                      "n_anom":len(anoms),"top_anoms":top[:4],"root_cause":rc,"expected_op":EXPECT[CASE]}))
