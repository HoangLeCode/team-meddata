import pandas as pd

# Load data
raw = pd.read_csv(
    "d652b210-ec3d-4a92-b7e0-e55c3dcbc7dc.csv",
    dtype={"Provider_Number": str}
)

# Make a copy
clean = raw.copy()

# Convert enrollment date to datetime
clean["Enroll_Status_Eff_DT"] = pd.to_datetime(
    clean["Enroll_Status_Eff_DT"],
    errors="coerce"
)

# Remove extra whitespace
for col in ["City", "State", "CountyName"]:
    clean[col] = clean[col].str.strip()

# Replace invalid (0, 0) coordinates with missing values
clean.loc[
    (clean["Latitude"] == 0) & (clean["Longitude"] == 0),
    ["Latitude", "Longitude"]
] = pd.NA

# Final checks
print("Shape:", clean.shape)
print("Missing CountyName:", clean["CountyName"].isna().sum())
print("Missing Latitude:", clean["Latitude"].isna().sum())
print("Missing Longitude:", clean["Longitude"].isna().sum())
print("Exact duplicates:", clean.duplicated().sum())

# Save cleaned data
clean.to_csv("clean_provider_data.csv", index=False)

# 8. Check suspicious values

print("Latitude range:",
      clean["Latitude"].min(),
      clean["Latitude"].max())

print("Longitude range:",
      clean["Longitude"].min(),
      clean["Longitude"].max())

print("Negative ZIP:",
      (clean["ZIP"] < 0).sum())

print("Negative Service Location Number:",
      (clean["Service_Location_Number"] < 0).sum())

print("Missing Provider Number:",
      clean["Provider_Number"].isna().sum())

print("Missing Provider Taxonomy:",
      clean["Provider_Taxonomy"].isna().sum())

print("Unique states:",
      clean["State"].nunique())

print("Unique provider taxonomy:",
      clean["Provider_Taxonomy"].nunique())

# 10. Reconcile changes

print("Original rows:", len(raw))
print("Final rows:", len(clean))
print("Row difference:", len(clean) - len(raw))

print("Original columns:", len(raw.columns))
print("Final columns:", len(clean.columns))

print(
    "Original zero-coordinate rows:",
    ((raw["Latitude"] == 0) & (raw["Longitude"] == 0)).sum()
)

print(
    "Final zero-coordinate rows:",
    ((clean["Latitude"] == 0) & (clean["Longitude"] == 0)).sum()
)

print(
    "Final missing-coordinate rows:",
    (clean["Latitude"].isna() & clean["Longitude"].isna()).sum()
)

# 12. Verify five individual records

check_indices = [0, 1, 590, 2768, 3279]

for i in check_indices:
    print("\nRecord:", i)

    print(
        "Original:",
        raw.loc[i, [
            "Provider_Number",
            "City",
            "State",
            "Latitude",
            "Longitude",
            "CountyName"
        ]].to_dict()
    )

    print(
        "Actual:",
        clean.loc[i, [
            "Provider_Number",
            "City",
            "State",
            "Latitude",
            "Longitude",
            "CountyName"
        ]].to_dict()
    )