#!/usr/bin/env python3
"""Canonical cleaning pipeline for the Medi-Cal FFS provider extract.

This is the ONE agreed cleaning path for the team. It reconciles the five
individual homework cleanings (see CLEANING_DECISIONS.md for every decision and
the evidence behind it).

    python clean_provider_data.py                       # medical.csv -> data/clean/
    python clean_provider_data.py --input path/to.csv

Outputs (the raw CSV is never modified):
    data/clean/providers_clean.parquet   the canonical analysis-ready dataset
    data/clean/cleaning_audit.json       source hash, row counts, per-rule counts

Design rules
------------
* No records are dropped. Rows are enrollment records, not unique providers;
  "how many providers" is a *counting rule* (distinct Provider_Number), never a
  row filter. See CLEANING_DECISIONS.md section 2.
* Missing is never invented. Placeholders become nulls; a *_status column says
  why a value is absent. Nothing is filled with "Unknown".
* Identifiers, ZIPs, FIPS and codes are strings (leading zeros matter).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

RAW_DEFAULT = Path("medical.csv")
OUT_DEFAULT = Path("data/clean/providers_clean.parquet")
AUDIT_DEFAULT = Path("data/clean/cleaning_audit.json")

# SHA-256 of the raw snapshot the team agreed on (372,778 rows). DHCS refreshes
# the dataset monthly, so a different hash means a different snapshot: the
# script warns but still runs.
CANONICAL_RAW_SHA256 = "5294e7c7cce6a42cc03812ece777fb5ce8b15f3352c3422573a46351dc08a29b"

# The 58 California counties, alphabetical. California county FIPS codes are the
# odd numbers 06001..06115 in this order; tests verify this against the data.
CA_COUNTIES = [
    "Alameda", "Alpine", "Amador", "Butte", "Calaveras", "Colusa", "Contra Costa",
    "Del Norte", "El Dorado", "Fresno", "Glenn", "Humboldt", "Imperial", "Inyo",
    "Kern", "Kings", "Lake", "Lassen", "Los Angeles", "Madera", "Marin", "Mariposa",
    "Mendocino", "Merced", "Modoc", "Mono", "Monterey", "Napa", "Nevada", "Orange",
    "Placer", "Plumas", "Riverside", "Sacramento", "San Benito", "San Bernardino",
    "San Diego", "San Francisco", "San Joaquin", "San Luis Obispo", "San Mateo",
    "Santa Barbara", "Santa Clara", "Santa Cruz", "Shasta", "Sierra", "Siskiyou",
    "Solano", "Sonoma", "Stanislaus", "Sutter", "Tehama", "Trinity", "Tulare",
    "Tuolumne", "Ventura", "Yolo", "Yuba",
]
CA_COUNTY_FIPS = {name: f"06{2 * i + 1:03d}" for i, name in enumerate(CA_COUNTIES)}

# Only real label error found in CountyName for California (FIPS 06037, ZIP 90095).
COUNTY_LABEL_FIXES = {"Los Ángeles": "Los Angeles County"}

# Disguised-missing tokens (compared case-insensitively after trimming).
GENERIC_PLACEHOLDERS = {"N/A", "NA", "NONE", "-"}
GENERIC_PLACEHOLDER_COLUMNS = [
    "ANC_Provider_Type", "NEMT_NMT_Provider_Type", "FI_Provider_Type_CD",
    "FI_Provider_Type", "Provider_License", "FI_Provider_Specialty_CD",
    "In_Out_State", "Address_Attention", "Address", "Address2", "City", "State",
    "ZIP", "ZIP_4", "Provider_Website", "Other_Languages", "Out_of_State_Indicator",
]
COLUMN_PLACEHOLDERS = {
    "Provider_Taxonomy": {"NO TAXONOMY PROVIDED", "TAXONOMY NOT APPLICABLE"},
    "FI_Provider_Type": {"UNKNOWN"},
    "Address_Attention": {".", "0"},
    "Address2": {"0"},
}

FLAG_COLUMNS = [
    "Telehealth_Services", "Medicaid_Patients", "CHIP_Patients", "Acc_Exam_Room",
    "Acc_Exterior_Building", "Acc_Interior_Building", "Acc_Parking", "Acc_Restroom",
    "Acc_Medical_Equipment", "Acc_Patient_Areas", "Acc_Patient_Diagnostic",
]
STRING_ID_COLUMNS = ["Provider_Number", "NPI", "FI_Provider_Type_CD",
                     "FI_Provider_Specialty_CD", "DHCS_County_CD", "FIPS_County_CD",
                     "Provider_Source"]
FORMAT_RULES = {  # column -> regex a non-null value must match (else nulled + counted)
    "NPI": r"\d{10}", "ZIP": r"\d{5}", "ZIP_4": r"\d{4}", "FIPS_County_CD": r"\d{5}",
}
DERIVED_COLUMNS = ["specialty_status", "geo_status", "state_conflict",
                   "ca_county", "ca_county_fips"]

REQUIRED_COLUMNS = {
    "_id", "Provider_Number", "NPI", "Owner_Number", "Service_Location_Number",
    "Enroll_Status_Eff_DT", "Provider_Taxonomy", "FI_Provider_Type", "FI_Provider_Specialty",
    "FI_Provider_Specialty_CD", "State", "ZIP", "CountyName", "Latitude", "Longitude",
    "Provider_Source", *FLAG_COLUMNS,
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _eq(series: pd.Series, value: str) -> pd.Series:
    """Null-safe equality: NA compares as False (never raises on masks)."""
    return (series == value).fillna(False).astype(bool)


def _isin(series: pd.Series, values: set[str]) -> pd.Series:
    return series.isin(list(values)).fillna(False).astype(bool)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_raw(path: Path) -> pd.DataFrame:
    """Read every column as text and treat ONLY empty cells as null.

    pandas' default parser silently converts the literal strings "N/A", "NA",
    "None" to NaN (88,998 rows in the agreed snapshot). Keeping them lets the
    rules below tell "not applicable" apart from "blank".
    """
    return pd.read_csv(path, dtype="string", keep_default_na=False,
                       na_values=[""], low_memory=False)


# --------------------------------------------------------------------------- #
# The cleaning function (pure: DataFrame in, DataFrame + audit out)
# --------------------------------------------------------------------------- #

def clean_providers(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    missing = sorted(REQUIRED_COLUMNS - set(raw.columns))
    if missing:
        raise ValueError(f"raw extract is missing required columns: {', '.join(missing)}")

    df = raw.copy(deep=True)
    audit: dict[str, Any] = {"rows_in": int(len(df)), "columns_in": int(df.shape[1])}

    # 1. Text: trim, collapse internal runs of whitespace, blank -> null. ------
    modified = 0
    for col in df.columns:
        before = df[col].astype("string")
        after = before.str.strip().str.replace(r"\s+", " ", regex=True)
        after = after.mask(after == "")
        modified += int((before.notna() & after.ne(before).fillna(False)).sum())
        df[col] = after
    audit["whitespace_cells_modified"] = modified

    # 2. Specialty status (must run BEFORE placeholders are nulled). ----------
    sp = df["FI_Provider_Specialty"]
    sp_up = sp.str.upper()
    status = pd.Series("specified", index=df.index, dtype="string")
    status[_eq(sp_up, "NOT APPLICABLE")] = "not_applicable"   # type has no specialty concept
    status[_eq(sp_up, "N/A")] = "not_recorded"                # Provider_Source 2/3 records
    status[sp.isna() | _eq(sp_up, "UNKNOWN")] = "missing"     # expected but absent
    df["specialty_status"] = status
    not_specified = status.ne("specified")
    df["FI_Provider_Specialty"] = sp.mask(not_specified)
    df["FI_Provider_Specialty_CD"] = df["FI_Provider_Specialty_CD"].mask(not_specified)
    audit["specialty_status"] = {k: int(v) for k, v in status.value_counts().items()}

    # 3. Placeholders -> null. -------------------------------------------------
    nulled: dict[str, int] = {}
    for col in GENERIC_PLACEHOLDER_COLUMNS:
        hit = _isin(df[col].str.upper(), GENERIC_PLACEHOLDERS)
        if hit.any():
            nulled[col] = nulled.get(col, 0) + int(hit.sum())
            df[col] = df[col].mask(hit)
    for col, tokens in COLUMN_PLACEHOLDERS.items():
        hit = _isin(df[col].str.upper(), tokens)
        if hit.any():
            nulled[col] = nulled.get(col, 0) + int(hit.sum())
            df[col] = df[col].mask(hit)
    audit["placeholder_cells_nulled"] = nulled

    # 4. Types. ----------------------------------------------------------------
    invalid: dict[str, int] = {}
    for col, pattern in FORMAT_RULES.items():
        bad = df[col].notna() & ~df[col].str.fullmatch(pattern).fillna(False)
        if bad.any():
            invalid[col] = int(bad.sum())
            df[col] = df[col].mask(bad)
    for col in ("_id", "Owner_Number", "Service_Location_Number"):
        numeric = pd.to_numeric(df[col], errors="coerce")
        bad = df[col].notna() & numeric.isna()
        if bad.any():
            invalid[col] = int(bad.sum())
        df[col] = numeric.astype("Int64")
    df["Out_of_State_Indicator"] = pd.to_numeric(
        df["Out_of_State_Indicator"], errors="coerce").astype("Int8")
    # Two DHCS export formats exist: "2011-01-19 0:00:00" (agreed snapshot) and
    # "1/19/2011" (a different pull). Anything else is an error, never a silent null.
    text = df["Enroll_Status_Eff_DT"]
    parsed = pd.to_datetime(text, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    retry = parsed.isna() & text.notna()
    if retry.any():
        parsed[retry] = pd.to_datetime(text[retry], format="%m/%d/%Y", errors="coerce")
    bad = text.notna() & parsed.isna()
    if bad.any():
        raise ValueError(f"{int(bad.sum())} Enroll_Status_Eff_DT values have an "
                         f"unrecognised format, e.g. {text[bad].iloc[0]!r}")
    df["Enroll_Status_Eff_DT"] = parsed.dt.normalize()
    for col in FLAG_COLUMNS:
        mapped = df[col].str.upper().map({"Y": True, "N": False})
        bad = df[col].notna() & mapped.isna()
        if bad.any():
            invalid[col] = int(bad.sum())
        df[col] = mapped.astype("boolean")
    for col in ("Latitude", "Longitude"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    audit["invalid_values_nulled"] = invalid

    # 5. Coordinates: (0, 0) is a "not geocoded" sentinel, not a location. ----
    zero = (df["Latitude"] == 0) & (df["Longitude"] == 0)
    out_of_range = ~df["Latitude"].between(-90, 90) | ~df["Longitude"].between(-180, 180)
    bad_coord = (zero | out_of_range.fillna(False)).fillna(False)
    df.loc[bad_coord, ["Latitude", "Longitude"]] = float("nan")
    audit["coordinates_nulled"] = int(bad_coord.sum())

    # 6. County label repair (only the one verified error). --------------------
    fix = df["CountyName"].isin(list(COUNTY_LABEL_FIXES))
    audit["county_labels_fixed"] = int(fix.sum())
    df["CountyName"] = df["CountyName"].replace(COUNTY_LABEL_FIXES)

    # 7. Derived geography. ----------------------------------------------------
    county = df["CountyName"]
    ca_name = county.str.removesuffix(" County")
    is_ca_label = _isin(ca_name, set(CA_COUNTIES)) & county.str.endswith(" County").fillna(False)
    in_ca_state = _eq(df["State"], "CA")
    geo = pd.Series("out_of_state", index=df.index, dtype="string")
    geo[county.isna()] = "unassigned"
    geo[in_ca_state & is_ca_label] = "california"
    df["geo_status"] = geo
    # State field says CA but the county/ZIP/coordinates are elsewhere (6 rows,
    # e.g. State=CA with a Cook County, IL address). Such rows are NOT California.
    df["state_conflict"] = (in_ca_state & county.notna() & ~is_ca_label).astype(bool)
    df["ca_county"] = ca_name.where(geo == "california")
    df["ca_county_fips"] = df["ca_county"].map(CA_COUNTY_FIPS).astype("string")
    # Out-of-state rows whose county NAME equals a California county ("Orange
    # County, FL"). Grouping by CountyName alone would count them as California.
    audit["name_collision_rows"] = int(((geo == "out_of_state") & is_ca_label).sum())
    audit["geo_status"] = {k: int(v) for k, v in geo.value_counts().items()}
    audit["state_conflict_rows"] = int(df["state_conflict"].sum())

    # 8. Drop the one fully redundant column; keep everything else. ------------
    if "OBJECTID" in raw.columns and (raw["OBJECTID"] == raw["_id"]).all():
        df = df.drop(columns=["OBJECTID"])
        audit["dropped_columns"] = ["OBJECTID (identical to _id)"]

    for col in STRING_ID_COLUMNS:
        df[col] = df[col].astype("string")
    df = df.sort_values("_id", kind="stable").reset_index(drop=True)

    audit["rows_out"] = int(len(df))
    audit["columns_out"] = int(df.shape[1])
    audit["null_counts_after"] = {c: int(n) for c, n in df.isna().sum().items() if n}
    return df, audit


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--input", type=Path, default=RAW_DEFAULT)
    parser.add_argument("--output", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--audit", type=Path, default=AUDIT_DEFAULT)
    args = parser.parse_args()

    if not args.input.is_file():
        raise FileNotFoundError(f"Raw file not found: {args.input}")

    digest = sha256_of(args.input)
    if digest != CANONICAL_RAW_SHA256:
        print("WARNING: raw file differs from the team's agreed snapshot "
              f"(sha256 {digest[:12]}...). Row counts will not match the docs.")

    raw = read_raw(args.input)
    print(f"Raw: {len(raw):,} rows x {raw.shape[1]} columns")
    clean, audit = clean_providers(raw)

    audit["source_sha256"] = digest
    audit["matches_agreed_snapshot"] = digest == CANONICAL_RAW_SHA256
    audit["latest_enrollment_date"] = str(clean["Enroll_Status_Eff_DT"].max().date())

    args.output.parent.mkdir(parents=True, exist_ok=True)
    clean.to_parquet(args.output, index=False, compression="zstd")
    args.audit.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")

    print(f"Clean: {len(clean):,} rows x {clean.shape[1]} columns -> {args.output}")
    print(f"  specialty_status: {audit['specialty_status']}")
    print(f"  geo_status:       {audit['geo_status']}")
    print(f"Audit written to {args.audit}")


if __name__ == "__main__":
    main()
