import pandas as pd

df = pd.read_csv(
    "clean_provider_data.csv",
    dtype={"Provider_Number": str}
)

print(df.shape)
print(df.head())

# Keep California providers only
ca = df[df["State"] == "CA"].copy()

print("California rows:", ca.shape)
print("California counties:", ca["CountyName"].nunique())