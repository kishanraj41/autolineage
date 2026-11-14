import pandas as pd

days = pd.date_range("2022-10-01", periods=6, freq="D")
df = pd.DataFrame({"day": days})
df["Vaccinated_1st"] = [9744650, 857, 582, 1200, 950, 9745232]  # fault
