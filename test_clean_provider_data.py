"""Checks for the canonical cleaning pipeline.

    pytest test_clean_provider_data.py

Part 1 (unit): one tiny synthetic frame per cleaning decision. Always runs.
Part 2 (data): integrity checks on data/clean/providers_clean.parquet. Skipped
               when the parquet has not been built.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import clean_provider_data as cpd

RAW_COLUMNS = [
    "_id", "OBJECTID", "Provider_Number", "NPI", "Owner_Number", "Service_Location_Number",
    "Legal_Name", "Enroll_Status_Eff_DT", "Provider_Taxonomy", "ANC_Provider_Type",
    "NEMT_NMT_Provider_Type", "FI_Provider_Type_CD", "FI_Provider_Type", "Provider_License",
    "FI_Provider_Specialty_CD", "FI_Provider_Specialty", "Out_of_State_Indicator",
    "In_Out_State", "Address_Attention", "Address", "Address2", "City", "State", "ZIP",
    "ZIP_4", "DHCS_County_CD", "FIPS_County_CD", "Phone_Number", "Medicaid_Patients",
    "CHIP_Patients", "Telehealth_Services", "Provider_Website", "Threshold_Languages",
    "Other_Languages", "Acc_Exam_Room", "Acc_Exterior_Building", "Acc_Interior_Building",
    "Acc_Parking", "Acc_Restroom", "Acc_Medical_Equipment", "Acc_Patient_Areas",
    "Acc_Patient_Diagnostic", "Provider_Source", "Latitude", "Longitude", "CountyName",
]


def make_raw(**overrides) -> pd.DataFrame:
    """Raw frame with one row per list item. Each override is a list of cell values."""
    n = len(next(iter(overrides.values())))
    base = {c: [pd.NA] * n for c in RAW_COLUMNS}
    base.update({
        "_id": [str(i + 1) for i in range(n)], "OBJECTID": [str(i + 1) for i in range(n)],
        "Provider_Number": ["1003000001"] * n, "Owner_Number": ["1"] * n,
        "Service_Location_Number": ["1"] * n,
        "Enroll_Status_Eff_DT": ["2011-01-19 0:00:00"] * n,
        "State": ["CA"] * n, "CountyName": ["Los Angeles County"] * n,
        "Latitude": ["34.06"] * n, "Longitude": ["-118.44"] * n,
        "FI_Provider_Specialty": ["Pediatrics"] * n, "FI_Provider_Specialty_CD": ["40"] * n,
        "Provider_Source": ["1"] * n,
    })
    base.update(overrides)
    return pd.DataFrame(base).astype("string")


def clean(**overrides) -> pd.DataFrame:
    return cpd.clean_providers(make_raw(**overrides))[0]


# ----------------------------------------------------------------------------
# Part 1: unit tests, one per decision
# ----------------------------------------------------------------------------

def test_no_rows_are_dropped_even_for_repeated_provider_location_keys():
    out = clean(FI_Provider_Specialty=["Pediatrics", "Internal Medicine"],
                FI_Provider_Specialty_CD=["40", "41"])
    assert len(out) == 2
    assert set(out["FI_Provider_Specialty"]) == {"Pediatrics", "Internal Medicine"}


@pytest.mark.parametrize("raw_value, status", [
    ("Pediatrics", "specified"),
    ("NOT APPLICABLE", "not_applicable"),
    ("N/A", "not_recorded"),
    ("Unknown", "missing"),
    ("UNKNOWN", "missing"),
    (pd.NA, "missing"),
])
def test_specialty_status_and_label(raw_value, status):
    out = clean(FI_Provider_Specialty=[raw_value])
    assert out.loc[0, "specialty_status"] == status
    if status == "specified":
        assert out.loc[0, "FI_Provider_Specialty"] == "Pediatrics"
    else:
        assert pd.isna(out.loc[0, "FI_Provider_Specialty"])
        assert pd.isna(out.loc[0, "FI_Provider_Specialty_CD"])


def test_literal_na_is_preserved_by_reader_then_classified(tmp_path: Path):
    csv = tmp_path / "raw.csv"
    make_raw(FI_Provider_Specialty=["N/A"]).to_csv(csv, index=False)
    raw = cpd.read_raw(csv)
    assert raw.loc[0, "FI_Provider_Specialty"] == "N/A"  # default pandas would make this NaN
    assert cpd.clean_providers(raw)[0].loc[0, "specialty_status"] == "not_recorded"


def test_placeholders_become_null_and_whitespace_is_normalised():
    out = clean(Provider_License=[" -"], Provider_Taxonomy=["No Taxonomy Provided"],
                FI_Provider_Type=["Unknown"], Legal_Name=["HOWELL, MYLA  LCSW "],
                City=[" DAVIS"], Address_Attention=["."])
    row = out.iloc[0]
    assert pd.isna(row["Provider_License"]) and pd.isna(row["Provider_Taxonomy"])
    assert pd.isna(row["FI_Provider_Type"]) and pd.isna(row["Address_Attention"])
    assert row["Legal_Name"] == "HOWELL, MYLA LCSW"
    assert row["City"] == "DAVIS"


def test_text_case_is_not_changed():
    out = clean(FI_Provider_Specialty=["Gastroenterology (M.D. only)"],
                CountyName=["Los Angeles County"])
    assert out.loc[0, "FI_Provider_Specialty"] == "Gastroenterology (M.D. only)"
    assert out.loc[0, "CountyName"] == "Los Angeles County"


def test_zero_zero_coordinates_become_null_but_real_out_of_state_ones_survive():
    out = clean(State=["CA", "TX"], CountyName=[pd.NA, "Harris County"],
                Latitude=["0", "29.76"], Longitude=["0", "-95.37"])
    assert out["Latitude"].isna().tolist() == [True, False]
    assert out.loc[1, "Longitude"] == pytest.approx(-95.37)


def test_county_label_typo_is_repaired_and_county_is_california():
    out = clean(CountyName=["Los Ángeles"])
    assert out.loc[0, "CountyName"] == "Los Angeles County"
    assert out.loc[0, "ca_county"] == "Los Angeles" and out.loc[0, "ca_county_fips"] == "06037"


def test_geo_status_uses_state_and_county_together():
    out = clean(
        State=["CA", "FL", "CA", "CA"],
        CountyName=["Orange County", "Orange County", pd.NA, "Cook County"],
        Latitude=["33.7", "28.5", "0", "41.8"], Longitude=["-117.8", "-81.3", "0", "-87.7"],
    )
    assert out["geo_status"].tolist() == ["california", "out_of_state", "unassigned", "out_of_state"]
    assert out["ca_county"].tolist()[0] == "Orange" and pd.isna(out["ca_county"].tolist()[1])
    assert out["state_conflict"].tolist() == [False, False, False, True]


def test_types_ids_are_strings_dates_are_dates_flags_are_boolean():
    out = clean(Provider_Number=["MSS00003F"], NPI=[pd.NA], ZIP=["02134"], ZIP_4=["0123"],
                FIPS_County_CD=["06037"], FI_Provider_Type_CD=["026"],
                Telehealth_Services=["Y"], Medicaid_Patients=["N"])
    row = out.iloc[0]
    assert row["Provider_Number"] == "MSS00003F"
    assert (row["ZIP"], row["ZIP_4"], row["FIPS_County_CD"], row["FI_Provider_Type_CD"]) == (
        "02134", "0123", "06037", "026")
    assert pd.api.types.is_datetime64_any_dtype(out["Enroll_Status_Eff_DT"])
    assert bool(row["Telehealth_Services"]) is True and bool(row["Medicaid_Patients"]) is False


def test_both_known_date_formats_parse_and_unknown_format_fails_loudly():
    ok = clean(Enroll_Status_Eff_DT=["2011-01-19 0:00:00", "1/19/2011"])
    assert ok["Enroll_Status_Eff_DT"].nunique() == 1
    with pytest.raises(ValueError, match="unrecognised format"):
        clean(Enroll_Status_Eff_DT=["19 Jan 2011"])


def test_missing_required_column_fails_with_clear_message():
    with pytest.raises(ValueError, match="missing required columns"):
        cpd.clean_providers(make_raw(State=["CA"]).drop(columns=["Latitude"]))


def test_ca_county_fips_are_the_58_odd_codes_06001_to_06115():
    assert len(cpd.CA_COUNTIES) == 58 == len(set(cpd.CA_COUNTIES))
    assert cpd.CA_COUNTY_FIPS["Alameda"] == "06001" and cpd.CA_COUNTY_FIPS["Yuba"] == "06115"
    assert cpd.CA_COUNTY_FIPS["Los Angeles"] == "06037" and cpd.CA_COUNTY_FIPS["Orange"] == "06059"


# ----------------------------------------------------------------------------
# Part 2: integrity of the real canonical dataset
# ----------------------------------------------------------------------------

CLEAN_PATH = Path("data/clean/providers_clean.parquet")
AUDIT_PATH = Path("data/clean/cleaning_audit.json")
needs_data = pytest.mark.skipif(not CLEAN_PATH.exists(),
                                reason="run clean_provider_data.py to build the parquet")


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return pd.read_parquet(CLEAN_PATH)


@pytest.fixture(scope="module")
def audit() -> dict:
    return json.loads(AUDIT_PATH.read_text())


@needs_data
def test_every_raw_record_is_kept_and_ids_are_unique(df, audit):
    assert len(df) == audit["rows_in"] == audit["rows_out"]
    assert df["_id"].is_unique


@needs_data
def test_exactly_58_california_counties_with_matching_fips(df):
    ca = df[df["geo_status"] == "california"]
    assert ca["ca_county"].nunique() == 58
    assert set(ca["ca_county"]) == set(cpd.CA_COUNTIES)
    # Independent cross-check: the source's own FIPS (ignoring its 06000 placeholder)
    # agrees with our county -> FIPS table for every county.
    src = ca[ca["FIPS_County_CD"].notna() & (ca["FIPS_County_CD"] != "06000")]
    modal = src.groupby("ca_county")["FIPS_County_CD"].agg(lambda s: s.value_counts().index[0])
    assert (modal == ca.groupby("ca_county")["ca_county_fips"].first().reindex(modal.index)).all()


@needs_data
def test_california_means_state_ca_and_never_a_state_conflict(df):
    ca = df[df["geo_status"] == "california"]
    assert (ca["State"] == "CA").all()
    assert not df.loc[df["state_conflict"], "geo_status"].eq("california").any()


@needs_data
def test_county_name_alone_is_not_enough_to_identify_california(df):
    """Out-of-state rows can share a California county's name (Orange County, FL)."""
    names = {c + " County" for c in cpd.CA_COUNTIES}
    collide = df[(df["geo_status"] == "out_of_state") & df["CountyName"].isin(names)]
    assert len(collide) > 0


@needs_data
def test_no_fake_coordinates_and_coordinate_nulls_match_unassigned_rows(df):
    assert not ((df["Latitude"] == 0) & (df["Longitude"] == 0)).any()
    assert df["Latitude"].isna().sum() == (df["geo_status"] == "unassigned").sum()
    assert df.loc[df["geo_status"] == "out_of_state", "Latitude"].notna().all()


@needs_data
def test_specialty_label_exists_exactly_when_status_is_specified(df):
    assert set(df["specialty_status"]) == {"specified", "not_applicable", "not_recorded", "missing"}
    assert (df["FI_Provider_Specialty"].notna() == (df["specialty_status"] == "specified")).all()
    assert not df["FI_Provider_Specialty"].isin(["Unknown", "UNKNOWN", "NOT APPLICABLE", "N/A"]).any()


@needs_data
def test_identifier_and_code_columns_keep_leading_zeros(df):
    assert df["ZIP"].dropna().str.fullmatch(r"\d{5}").all()
    assert df["ZIP_4"].dropna().str.fullmatch(r"\d{4}").all()
    assert df["FIPS_County_CD"].dropna().str.fullmatch(r"\d{5}").all()
    assert df["FI_Provider_Type_CD"].dropna().str.fullmatch(r"\d{3}").all()
    assert df["Provider_Number"].notna().all()
    assert df["Provider_Number"].str.startswith("MSS").sum() > 0


@needs_data
def test_no_text_column_has_stray_whitespace_or_empty_strings(df):
    for col in df.select_dtypes(include=["string", "object"]).columns:
        s = df[col].dropna()
        assert (s == s.str.strip()).all(), f"{col} has leading/trailing whitespace"
        assert not s.str.contains(r"\s{2,}").any(), f"{col} has repeated spaces"
        assert (s != "").all(), f"{col} has empty strings"


@needs_data
def test_rows_are_not_providers_counting_rule_is_distinct_provider_number(df):
    ca = df[df["geo_status"] == "california"]
    assert ca["Provider_Number"].nunique() < len(ca)
    la = ca[ca["ca_county"] == "Los Angeles"]
    assert la["Provider_Number"].nunique() < len(la)
