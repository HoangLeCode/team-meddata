# %%
import pandas as pd

raw = pd.read_csv(
    "data_cleaning/data/medi-cal.csv",
    low_memory=False
)

df = raw.copy()

print("Rows:", df.shape[0])
print("Columns:", df.shape[1])

df.head()

# %%

# Inspect every column
column_check = pd.DataFrame({
    "data_type": df.dtypes,
    "missing_count": df.isna().sum(),
    "unique_values": df.nunique()
})

column_check

# %%
df.columns.tolist()

# %%
# Check exact duplicate rows
exact_duplicates = df.duplicated().sum()

# Check repeated provider-location identifiers
id_columns = [
    "Provider_Number",
    "Owner_Number",
    "Service_Location_Number"
]

repeated_ids = df.duplicated(
    subset=id_columns,
    keep=False
).sum()

print("Exact duplicate rows:", exact_duplicates)
print("Rows with repeated provider-location IDs:", repeated_ids)

# %%
# View examples of repeated provider-location IDs
repeated_records = (
    df[df.duplicated(subset=id_columns, keep=False)]
    .sort_values(id_columns)
)

repeated_records[
    id_columns
    + [
        "NPI",
        "Legal_Name",
        "Enroll_Status_Eff_DT",
        "Provider_Taxonomy",
        "FI_Provider_Specialty",
        "Address",
        "City",
        "ZIP"
    ]
].head(20)

# %%
# Save important original values for before/after checks
before_cleaning = df.copy()

# 1. Clean spaces in all text columns
text_columns = df.select_dtypes(include=["object", "string"]).columns

for column in text_columns:
    df[column] = (
        df[column]
        .astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )

# Convert blank text into missing values
df[text_columns] = df[text_columns].replace("", pd.NA)


# 2. Clean ID columns and preserve them as text
# Keep Provider_Number as text
df["Provider_Number"] = (
    df["Provider_Number"]
    .astype("string")
    .str.strip()
)

# Clean the other identifier columns
numeric_identifier_columns = [
    "NPI",
    "Owner_Number",
    "Service_Location_Number"
]

for column in numeric_identifier_columns:
    df[column] = (
        pd.to_numeric(df[column], errors="coerce")
        .astype("Int64")
        .astype("string")
    )

# 3. Clean ZIP as a five-character identifier
df["ZIP"] = (
    pd.to_numeric(df["ZIP"], errors="coerce")
    .astype("Int64")
    .astype("string")
    .str.zfill(5)
)


# 4. Convert the enrollment date into a real date
df["Enroll_Status_Eff_DT"] = pd.to_datetime(
    df["Enroll_Status_Eff_DT"],
    errors="coerce"
)


# 5. Standardize state and county text
df["State"] = df["State"].str.upper()
df["CountyName"] = df["CountyName"].str.title()


print("Basic cleaning completed.")
print("Rows after cleaning:", len(df))
print("No rows have been removed.")

# %%
# Check failed date conversions
original_dates_present = before_cleaning["Enroll_Status_Eff_DT"].notna()
failed_date_conversions = (
    original_dates_present &
    df["Enroll_Status_Eff_DT"].isna()
).sum()

# Check ZIP codes
invalid_zip_count = (
    df["ZIP"].notna() &
    ~df["ZIP"].str.fullmatch(r"\d{5}", na=False)
).sum()

# Check impossible latitude and longitude values
invalid_latitude_count = (
    df["Latitude"].notna() &
    ~df["Latitude"].between(-90, 90)
).sum()

invalid_longitude_count = (
    df["Longitude"].notna() &
    ~df["Longitude"].between(-180, 180)
).sum()

# Check future enrollment dates
future_date_count = (
    df["Enroll_Status_Eff_DT"] >
    pd.Timestamp.today().normalize()
).sum()

print("Failed date conversions:", failed_date_conversions)
print("Invalid ZIP codes:", invalid_zip_count)
print("Invalid latitudes:", invalid_latitude_count)
print("Invalid longitudes:", invalid_longitude_count)
print("Future enrollment dates:", future_date_count)

print("\nEnrollment date range:")
print(df["Enroll_Status_Eff_DT"].min())
print(df["Enroll_Status_Eff_DT"].max())

print("\nMost common states:")
print(df["State"].value_counts(dropna=False).head(10))

# %%
# Compare missing values before and after cleaning
missing_before = before_cleaning.isna().sum()
missing_after = df.isna().sum()

missing_check = pd.DataFrame({
    "missing_before": missing_before,
    "missing_after": missing_after,
    "change": missing_after - missing_before
})

missing_check = missing_check[
    (missing_check["missing_before"] > 0) |
    (missing_check["missing_after"] > 0)
]

missing_check

# %%
# Save the full cleaned dataset
df.to_csv("cleaned_medi_cal.csv", index=False)

# Select up to 50 reproducible sample rows
cleaned_sample = df.sample(
    n=min(50, len(df)),
    random_state=576
)

cleaned_sample.to_csv(
    "cleaned_medi_cal_sample.csv",
    index=False
)

print("Full cleaned rows saved:", len(df))
print("Sample rows saved:", len(cleaned_sample))

# %%
# ------------------------------------------------------------
# FIVE INDIVIDUAL RECORD CHECKS
# ------------------------------------------------------------

# 1. A repeated provider-location ID
repeated_index = repeated_records.index[0]

# 2. A record with a missing state
missing_state_index = df[df["State"].isna()].index[0]

# 3. An out-of-state provider
out_of_state_index = df[
    df["State"].notna() & (df["State"] != "CA")
].index[0]

# 4. The record with the earliest enrollment date
earliest_date_index = df["Enroll_Status_Eff_DT"].idxmin()

# 5. A standard California record
standard_index = df[
    (df["State"] == "CA") &
    df["ZIP"].notna() &
    df["CountyName"].notna()
].index[0]

check_indices = [
    repeated_index,
    missing_state_index,
    out_of_state_index,
    earliest_date_index,
    standard_index
]

record_checks = pd.DataFrame({
    "check": [
        "Repeated provider-location ID",
        "Missing state",
        "Out-of-state provider",
        "Earliest enrollment date",
        "Standard California record"
    ],
    "reason": [
        "Repeated IDs may contain different valid enrollment or specialty information",
        "Missing state should remain missing instead of being invented",
        "Out-of-state providers may be valid and should not automatically be removed",
        "An old date is unusual but not automatically incorrect",
        "A normal record should remain available after cleaning"
    ],
    "original_value": [
        str(before_cleaning.loc[repeated_index, id_columns].to_dict()),
        before_cleaning.loc[missing_state_index, "State"],
        before_cleaning.loc[out_of_state_index, "State"],
        before_cleaning.loc[earliest_date_index, "Enroll_Status_Eff_DT"],
        before_cleaning.loc[standard_index, "ZIP"]
    ],
    "expected_result": [
        "Keep the record",
        "Keep as missing",
        "Keep the record",
        "Keep valid historical date",
        "Five-character ZIP"
    ],
    "actual_result": [
        "Record kept" if repeated_index in df.index else "Record removed",
        df.loc[missing_state_index, "State"],
        df.loc[out_of_state_index, "State"],
        df.loc[earliest_date_index, "Enroll_Status_Eff_DT"],
        df.loc[standard_index, "ZIP"]
    ],
    "matches_expected": [
        repeated_index in df.index,
        pd.isna(df.loc[missing_state_index, "State"]),
        out_of_state_index in df.index,
        pd.notna(df.loc[earliest_date_index, "Enroll_Status_Eff_DT"]),
        len(df.loc[standard_index, "ZIP"]) == 5
    ]
})

record_checks

# %%
# Include the five checked records, then add 45 reproducible random records
difficult_rows = df.loc[check_indices]

remaining_rows = df.drop(index=check_indices).sample(
    n=45,
    random_state=576
)

cleaned_sample = pd.concat(
    [difficult_rows, remaining_rows],
    ignore_index=True
)

cleaned_sample.to_csv(
    "cleaned_medi_cal_sample.csv",
    index=False
)

record_checks.to_csv(
    "five_record_checks.csv",
    index=False
)

print("Five record checks saved.")
print("Improved 50-row sample saved.")

# %%
cleaning_decision_log = pd.DataFrame({
    "cleaning_rule": [
        "Trim leading, trailing, and repeated spaces in text columns",
        "Convert blank strings to missing values",
        "Store provider identifiers as text",
        "Store ZIP codes as five-character text",
        "Convert enrollment dates to datetime",
        "Standardize state abbreviations to uppercase",
        "Standardize county names to title case",
        "Keep repeated provider-location IDs",
        "Keep missing values",
        "Keep valid out-of-state providers"
    ],
    "reason": [
        "Prevents one value from appearing as multiple categories because of spacing",
        "Blank strings and missing values should be represented consistently",
        "Identifiers are labels and should not be used in calculations",
        "ZIP codes are identifiers and leading zeros are meaningful",
        "Allows dates to be checked and analyzed correctly",
        "Prevents values such as ca and CA from becoming separate categories",
        "Makes county categories consistent",
        "Repeated IDs may represent different specialties or enrollment records",
        "Missing information should not be invented",
        "The dataset legitimately contains enrolled providers outside California"
    ],
    "verification_check": [
        "Compared text before and after cleaning",
        "Compared missing counts before and after cleaning",
        "Checked identifier data types after conversion",
        "Confirmed every nonmissing ZIP has five digits",
        "Confirmed zero failed date conversions",
        "Reviewed state value counts",
        "Reviewed county values",
        "Found 71,084 repeated-ID rows and inspected examples",
        "Reported missing counts without dropping rows",
        "Reviewed out-of-state records and kept them"
    ]
})

cleaning_decision_log.to_csv(
    "cleaning_decision_log.csv",
    index=False
)

cleaning_decision_log

# %%
# Final reconciliation
starting_rows = len(raw)
final_rows = len(df)
rows_removed = starting_rows - final_rows

# Main project metrics
provider_location_records = len(df)
unique_providers = df["Provider_Number"].nunique(dropna=True)
records_with_county = df["CountyName"].notna().sum()
records_missing_county = df["CountyName"].isna().sum()

verification_summary = pd.DataFrame({
    "check": [
        "Starting rows",
        "Final rows",
        "Rows removed",
        "Exact duplicates",
        "Rows with repeated provider-location IDs",
        "Provider-location records",
        "Unique providers",
        "Records included in county analysis",
        "Records excluded from county analysis because county is missing"
    ],
    "result": [
        starting_rows,
        final_rows,
        rows_removed,
        exact_duplicates,
        repeated_ids,
        provider_location_records,
        unique_providers,
        records_with_county,
        records_missing_county
    ]
})

verification_summary.to_csv(
    "verification_summary.csv",
    index=False
)

verification_summary

# %%
print("Missing county count:", df["CountyName"].isna().sum())
print(
    "Records with county:",
    df["CountyName"].notna().sum()
)
print(
    "Unique provider count:",
    df["Provider_Number"].nunique(dropna=True)
)

# %%
# Display the five record checks as a readable table

record_check_table = record_checks.rename(columns={
    "check": "Record checked",
    "original_value": "Original value",
    "expected_result": "Expected result",
    "actual_result": "Actual result",
    "matches_expected": "Matched?"
}).copy()

record_check_table["Original value"] = (
    record_check_table["Original value"]
    .fillna("Missing (NaN)")
)

record_check_table["Actual result"] = (
    record_check_table["Actual result"]
    .fillna("Missing (<NA>)")
)

display(
    record_check_table.style
    .set_properties(**{
        "text-align": "left",
        "white-space": "normal"
    })
    .set_table_styles([{
        "selector": "th",
        "props": [
            ("text-align", "left"),
            ("background-color", "#dddddd")
        ]
    }])
    .hide(axis="index")
)

