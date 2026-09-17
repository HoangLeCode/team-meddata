import pandas as pd

# Load a manageable sample of 10,000 rows
providers = pd.read_csv(
    "medical.csv",  # use the actual CSV filename on your computer
    nrows=10000
)

# Check missing values in fields relevant to our project
key_columns = [
    "Provider_Number",
    "Service_Location_Number",
    "CountyName",
    "FI_Provider_Specialty",
    "Telehealth_Services",
    "Threshold_Languages",
    "Latitude",
    "Longitude"
]

print("MISSING-VALUE RATE")
print(providers[key_columns].isna().mean().sort_values())

print("\nTOP 10 COUNTIES")
print(providers["CountyName"].value_counts().head(10))

print("\nTOP 20 SPECIALTIES")
print(providers["FI_Provider_Specialty"].value_counts().head(20))

# Determine whether each row represents one unique provider or provider location
print("\nROW/IDENTIFIER CHECK")
print("Rows:", len(providers))
print("Unique provider numbers:", providers["Provider_Number"].nunique())

print(
    "Unique provider + service-location combinations:",
    providers[
        ["Provider_Number", "Service_Location_Number"]
    ].drop_duplicates().shape[0]
)

print(
    "Unique provider + location + specialty combinations:",
    providers[
        [
            "Provider_Number",
            "Service_Location_Number",
            "FI_Provider_Specialty"
        ]
    ].drop_duplicates().shape[0]
)

# Inspect a provider that appears more than once
print("\nEXAMPLE OF A REPEATED PROVIDER")
print(
    providers.loc[
        providers["Provider_Number"].eq(1003000563),
        [
            "Provider_Number",
            "Service_Location_Number",
            "FI_Provider_Specialty",
            "FI_Provider_Type",
            "CountyName"
        ]
    ]
)