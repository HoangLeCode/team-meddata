import pandas as pd


# ============================================================
# 1. LOAD ORIGINAL DATA
# ============================================================

medical = pd.read_csv("medical.csv", low_memory=False)

starting_rows = len(medical)

print("DATASET SHAPE")
print(medical.shape)


# ============================================================
# 2. INSPECT COLUMN TYPES
#    Checklist #4
# ============================================================

print("\nCOLUMN TYPES BEFORE CLEANING")
print(medical.dtypes)


# ============================================================
# 3. CHECK MISSING VALUES BEFORE CLEANING
#    Checklist #7
# ============================================================

missing_before = medical.isna().sum()

print("\nMISSING VALUES BEFORE CLEANING")
print(missing_before)


# ============================================================
# 4. CHECK DUPLICATES
#    Checklist #6
# ============================================================

exact_duplicates = medical.duplicated().sum()
provider_duplicates = medical["Provider_Number"].duplicated().sum()
id_duplicates = medical["_id"].duplicated().sum()
objectid_duplicates = medical["OBJECTID"].duplicated().sum()

print("\nDUPLICATE CHECK")
print("Exact duplicate rows:", exact_duplicates)
print("Repeated Provider_Number values:", provider_duplicates)
print("_id duplicates:", id_duplicates)
print("OBJECTID duplicates:", objectid_duplicates)


# ============================================================
# 5. CHECK AND CLEAN TEXT
#    Checklist #5
# ============================================================

city_with_spaces = (
    medical["City"].notna()
    & (medical["City"] != medical["City"].str.strip())
)

print("\nCITY VALUES WITH EXTRA SPACES BEFORE CLEANING")
print(city_with_spaces.sum())

print(
    medical.loc[
        city_with_spaces,
        ["_id", "City"]
    ]
)


# ------------------------------------------------------------
# Save 5 ORIGINAL records BEFORE cleaning.
# We need these later for Checklist #12.
# ------------------------------------------------------------

check_ids = [28449, 65686, 74431, 80478, 107422]

original_checks = medical.loc[
    medical["_id"].isin(check_ids),
    ["_id", "City"]
].copy()


# ------------------------------------------------------------
# Clean City
# ------------------------------------------------------------

medical["City"] = medical["City"].str.strip()


# ------------------------------------------------------------
# Verify City cleaning
# ------------------------------------------------------------

city_with_spaces_after = (
    medical["City"].notna()
    & (medical["City"] != medical["City"].str.strip())
)

print("\nCITY VALUES WITH EXTRA SPACES AFTER CLEANING")
print(city_with_spaces_after.sum())


# ============================================================
# 6. CONVERT ENROLLMENT DATE
#    Checklist #4
# ============================================================

date_test = pd.to_datetime(
    medical["Enroll_Status_Eff_DT"],
    errors="coerce"
)

failed_date_conversions = date_test.isna().sum()

print("\nDATE CONVERSION CHECK")
print("Failed date conversions:", failed_date_conversions)

medical["Enroll_Status_Eff_DT"] = date_test

print("Date type after cleaning:")
print(medical["Enroll_Status_Eff_DT"].dtype)


# ============================================================
# 7. CONVERT NPI TO AN IDENTIFIER TYPE
#    Checklist #4
# ============================================================

npi_as_number = pd.to_numeric(
    medical["NPI"],
    errors="coerce"
)

failed_npi_conversions = (
    npi_as_number.isna().sum()
    - medical["NPI"].isna().sum()
)

medical["NPI"] = (
    npi_as_number
    .astype("Int64")
    .astype("string")
)

print("\nNPI CHECK")
print("Failed NPI conversions:", failed_npi_conversions)
print("NPI type after cleaning:")
print(medical["NPI"].dtype)


# ============================================================
# 8. CHECK SUSPICIOUS VALUES
#    Checklist #8
# ============================================================

print("\nSUSPICIOUS VALUE CHECKS")

print(
    "Enrollment dates before 1900:",
    (medical["Enroll_Status_Eff_DT"] < "1900-01-01").sum()
)

print(
    "Enrollment dates after today:",
    (
        medical["Enroll_Status_Eff_DT"]
        > pd.Timestamp.today()
    ).sum()
)

print(
    "Latitude values equal to 0:",
    (medical["Latitude"] == 0).sum()
)

print(
    "Longitude values equal to 0:",
    (medical["Longitude"] == 0).sum()
)

print(
    "Missing CountyName:",
    medical["CountyName"].isna().sum()
)

print("\nSUSPICIOUS GEOGRAPHIC RECORD CHECK")

geo_problem = (
    (medical["Latitude"] == 0)
    & (medical["Longitude"] == 0)
    & (medical["CountyName"].isna())
)

print("Records with all three conditions:", geo_problem.sum())

print(
    medical.loc[
        geo_problem,
        [
            "_id",
            "Provider_Number",
            "State",
            "ZIP",
            "CountyName",
            "Latitude",
            "Longitude"
        ]
    ].head(10)
)

# ============================================================
# 9. CHECK MISSING VALUES AFTER CLEANING
#    Checklist #7
# ============================================================

missing_after = medical.isna().sum()

print("\nMISSING VALUES AFTER CLEANING")
print(missing_after)


# ============================================================
# 10. RECONCILE ROW COUNTS
#     Checklist #10
# ============================================================

final_rows = len(medical)

print("\nROW COUNT RECONCILIATION")
print("Starting rows:", starting_rows)
print("Final rows:", final_rows)
print("Rows removed:", starting_rows - final_rows)


# ============================================================
# 11. CHECK CALCULATION DENOMINATORS
#     Checklist #11
# ============================================================

print("\nCALCULATION / DENOMINATOR CHECKS")

print(
    "Total provider records:",
    len(medical)
)

print(
    "Records with CountyName:",
    medical["CountyName"].notna().sum()
)

print(
    "Records with Provider_Taxonomy:",
    medical["Provider_Taxonomy"].notna().sum()
)

print(
    "Records with NPI:",
    medical["NPI"].notna().sum()
)


# ============================================================
# 12. FIVE RECORD CHECKS
#     Checklist #12
# ============================================================

record_checks = original_checks.copy()

record_checks["Expected"] = (
    record_checks["City"].str.strip()
)

record_checks["Actual"] = record_checks["_id"].map(
    medical.set_index("_id")["City"]
)

record_checks["Match"] = (
    record_checks["Expected"]
    == record_checks["Actual"]
)

# Make spaces visible in the output
record_checks["Original"] = record_checks["City"].map(repr)
record_checks["Expected"] = record_checks["Expected"].map(repr)
record_checks["Actual"] = record_checks["Actual"].map(repr)

record_checks = record_checks[
    ["_id", "Original", "Expected", "Actual", "Match"]
]

print("\nFIVE RECORD CHECKS")
print(record_checks.to_string(index=False))

# ============================================================
# 13. SAVE CLEANED DATA
# ============================================================

medical.to_csv(
    "medical_cleaned.csv",
    index=False
)

print("\nCLEANED DATA SAVED")
print("medical_cleaned.csv")


# ============================================================
# 14. CREATE 50-ROW SAMPLE FOR SUBMISSION
#
# Include the difficult City cases plus other cleaned records.
# ============================================================

difficult_cases = medical.loc[
    medical["_id"].isin(check_ids)
]

other_cases = medical.loc[
    ~medical["_id"].isin(check_ids)
].head(45)

sample = pd.concat(
    [difficult_cases, other_cases],
    ignore_index=True
)

sample.to_csv(
    "medical_cleaned_sample_50.csv",
    index=False
)

print("\n50-ROW SAMPLE SAVED")
print("medical_cleaned_sample_50.csv")
print("Sample rows:", len(sample))


# ============================================================
# FINAL COLUMN TYPES
# ============================================================

print("\nCOLUMN TYPES AFTER CLEANING")
print(medical.dtypes)