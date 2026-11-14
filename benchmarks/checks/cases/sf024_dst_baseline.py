import pandas as pd

hours = pd.date_range("2024-11-03", periods=6, freq="h")
frame = pd.DataFrame({"timestamp": hours, "temp": range(6)})
ordered = frame.sort_values("timestamp")
