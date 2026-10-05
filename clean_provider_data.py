import pandas as pd

raw = pd.read_csv("d652b210-ec3d-4a92-b7e0-e55c3dcbc7dc.csv")

print(raw.shape)
print(raw.head())
print(raw.columns.tolist())
print(raw.dtypes)
print(raw["Provider_Number"].apply(type).value_counts())
string_provider = raw[raw["Provider_Number"].apply(lambda x: isinstance(x, str))]

print(string_provider["Provider_Number"].head(20))
clean = raw.copy()

clean["Provider_Number"] = clean["Provider_Number"].astype(str)

print(clean["Provider_Number"].apply(type).value_counts())
print(clean.isna().sum().sort_values(ascending=False))
print(clean[clean["CountyName"].isna()][
    ["Provider_Number", "Service_Location_Number", "City", "State",
     "ZIP", "Latitude", "Longitude", "CountyName"]
].head(20))
print("Exact duplicate rows:", clean.duplicated().sum())

print(
    "Duplicate provider-location pairs:",
    clean.duplicated(
        subset=["Provider_Number", "Service_Location_Number"]
    ).sum()
)
dup_pairs = clean[
    clean.duplicated(
        subset=["Provider_Number", "Service_Location_Number"],
        keep=False
    )
]

print(
    dup_pairs[
        ["Provider_Number", "Service_Location_Number",
         "Provider_Taxonomy", "FI_Provider_Specialty", "CountyName"]
    ].head(20)
)
first_provider = dup_pairs.iloc[0]["Provider_Number"]
first_location = dup_pairs.iloc[0]["Service_Location_Number"]

example = clean[
    (clean["Provider_Number"] == first_provider) &
    (clean["Service_Location_Number"] == first_location)
]

print(example.to_string())

print(clean["Enroll_Status_Eff_DT"].head(20))

clean["Enroll_Status_Eff_DT"] = pd.to_datetime(
    clean["Enroll_Status_Eff_DT"],
    errors="coerce"
)

print(clean["Enroll_Status_Eff_DT"].dtype)
print(clean["Enroll_Status_Eff_DT"].isna().sum())

print(clean["State"].value_counts(dropna=False).head(20))
print(clean["City"].dropna().head(20))
print(clean["CountyName"].dropna().head(20))

print("City whitespace:",
      (clean["City"].dropna() != clean["City"].dropna().str.strip()).sum())

print("State whitespace:",
      (clean["State"].dropna() != clean["State"].dropna().str.strip()).sum())

print("CountyName whitespace:",
      (clean["CountyName"].dropna() != clean["CountyName"].dropna().str.strip()).sum())

print("Zero latitude:", (clean["Latitude"] == 0).sum())
print("Zero longitude:", (clean["Longitude"] == 0).sum())

print(
    "Both zero:",
    ((clean["Latitude"] == 0) & (clean["Longitude"] == 0)).sum()
)

missing_county = clean["CountyName"].isna()
zero_coords = (clean["Latitude"] == 0) & (clean["Longitude"] == 0)

print("Missing CountyName:", missing_county.sum())
print("Zero coordinates:", zero_coords.sum())
print("Both conditions:", (missing_county & zero_coords).sum())

problem_rows = clean[
    clean["CountyName"].isna()
    & (clean["Latitude"] == 0)
    & (clean["Longitude"] == 0)
]

print(problem_rows[
    [
        "Provider_Number",
        "Service_Location_Number",
        "City",
        "State",
        "ZIP",
        "DHCS_County_CD",
        "FIPS_County_CD",
        "CountyName"
    ]
].head(20))

county_map = (
    clean[clean["CountyName"].notna()]
    [["DHCS_County_CD", "CountyName"]]
    .drop_duplicates()
    .sort_values("DHCS_County_CD")
)

print(county_map.head(30))
print("Number of mappings:", len(county_map))

print(
    problem_rows["DHCS_County_CD"]
    .value_counts()
    .sort_index()
)

print("Problem rows FIPS missing:",
      problem_rows["FIPS_County_CD"].isna().sum())

print(
    problem_rows["FIPS_County_CD"]
    .value_counts(dropna=False)
    .sort_index()
)

print("Problem rows FIPS missing:",
      problem_rows["FIPS_County_CD"].isna().sum())

print(
    problem_rows["FIPS_County_CD"]
    .value_counts(dropna=False)
    .sort_index()
)

fips_map = (
    clean[
        clean["CountyName"].notna()
        & clean["FIPS_County_CD"].notna()
        & (clean["FIPS_County_CD"] != 6000)
    ][["FIPS_County_CD", "CountyName"]]
    .drop_duplicates()
    .sort_values("FIPS_County_CD")
)

print(fips_map.head(30))
print("Number of FIPS mappings:", len(fips_map))

print(
    clean[
        [
            "City",
            "State",
            "ZIP",
            "DHCS_County_CD",
            "FIPS_County_CD",
            "Latitude",
            "Longitude",
            "CountyName"
        ]
    ].head(20).to_string()
)

# =========================
# FINAL CLEANING
# =========================

# Convert Provider_Number to string
clean["Provider_Number"] = clean["Provider_Number"].astype(str)

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
# Check the cleaned data
print("Shape:", clean.shape)
print("Missing CountyName:", clean["CountyName"].isna().sum())
print("Missing Latitude:", clean["Latitude"].isna().sum())
print("Missing Longitude:", clean["Longitude"].isna().sum())
print("Exact duplicates:", clean.duplicated().sum())

# Check missing CountyName rows with valid FIPS codes

missing_county = clean[clean["CountyName"].isna()]

print("Total missing CountyName:", len(missing_county))

print(
    "Missing CountyName with FIPS:",
    missing_county["FIPS_County_CD"].notna().sum()
)

print(
    "Missing CountyName without FIPS:",
    missing_county["FIPS_County_CD"].isna().sum()
)

print(
    missing_county[
        ["State", "City", "ZIP", "FIPS_County_CD"]
    ].head(20)
)
# Check states for missing CountyName rows
print(
    missing_county["State"]
    .value_counts(dropna=False)
)

# Check whether missing-county providers have other rows with county information

missing_providers = clean.loc[
    clean["CountyName"].isna(),
    "Provider_Number"
]

provider_matches = clean[
    clean["Provider_Number"].isin(missing_providers)
]

print("Missing county rows:", clean["CountyName"].isna().sum())

print(
    "Missing-county providers with another known CountyName:",
    provider_matches.groupby("Provider_Number")["CountyName"]
    .apply(lambda x: x.notna().any())
    .sum()
)

print(
    provider_matches[
        ["Provider_Number", "Service_Location_Number",
         "City", "State", "ZIP", "CountyName"]
    ].sort_values("Provider_Number").head(40).to_string()
)

# Examine providers that have both missing and known CountyName

provider_county_info = (
    provider_matches
    .groupby("Provider_Number")
    .agg(
        total_rows=("CountyName", "size"),
        known_counties=("CountyName", lambda x: x.dropna().nunique()),
        missing_counties=("CountyName", lambda x: x.isna().sum())
    )
)

usable_providers = provider_county_info[
    (provider_county_info["known_counties"] == 1) &
    (provider_county_info["missing_counties"] > 0)
]

print("Providers with exactly one known CountyName:",
      len(usable_providers))

print(usable_providers.head(30))

# Check whether the same provider-location pair has a known CountyName

known_location = clean[
    clean["CountyName"].notna()
][
    ["Provider_Number", "Service_Location_Number", "CountyName"]
]

missing_location = clean[
    clean["CountyName"].isna()
][
    ["Provider_Number", "Service_Location_Number"]
]

matched = missing_location.merge(
    known_location,
    on=["Provider_Number", "Service_Location_Number"],
    how="left"
)

print("Missing rows:", len(missing_location))
print("Matched by provider + location:",
      matched["CountyName"].notna().sum())

print(
    matched[matched["CountyName"].notna()]
    .head(20)
    .to_string()
)

# Final sanity checks

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

print("Unique states:",
      clean["State"].nunique())

print("Unique provider taxonomy:",
      clean["Provider_Taxonomy"].nunique())

print("Final shape:", clean.shape)