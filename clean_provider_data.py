#!/usr/bin/env python3
"""Clean the provider extract while leaving the raw medical.csv unchanged.

Run from this directory:
    python clean_provider_data.py

The script writes only ``cleaned_sample_50.csv`` (or the output path supplied
on the command line).  It intentionally does not overwrite medical.csv.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


TEXT_COLUMNS = ("CountyName", "FI_Provider_Specialty")
KEY_COLUMNS = ("Provider_Number", "Service_Location_Number")
COORDINATE_LIMITS = {
    "Latitude": (32.5, 42.0),
    "Longitude": (-124.5, -114.1),
}
YES_VALUES = {"Y", "YES", "TRUE", "T", "1"}
NO_VALUES = {"N", "NO", "FALSE", "F", "0"}


def require_columns(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    """Fail early with an understandable error if the extract schema changed."""
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"medical.csv is missing required columns: {', '.join(missing)}")


def null_count(frame: pd.DataFrame) -> int:
    """Return the total number of null cells across the data frame."""
    return int(frame.isna().sum().sum())


def audit_step(
    name: str,
    rows_before: int,
    nulls_before: int,
    frame_after: pd.DataFrame,
    modified_cells: int = 0,
    rows_dropped: int = 0,
) -> None:
    """Print a consistent, exact before/after audit entry for one operation."""
    rows_after = len(frame_after)
    nulls_after = null_count(frame_after)
    print(f"\n[{name}]")
    print(f"  Records: {rows_before:,} -> {rows_after:,} (change: {rows_after - rows_before:+,})")
    print(f"  Null cells: {nulls_before:,} -> {nulls_after:,} (change: {nulls_after - nulls_before:+,})")
    print(f"  Rows dropped: {rows_dropped:,}; cells modified: {modified_cells:,}")


def display_value(value: Any) -> str:
    """Make nulls unambiguous in the verification report."""
    return "<NULL>" if pd.isna(value) else repr(value)


def clean_provider_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Return a cleaned copy and five-or-more auditable before/after examples."""
    required = set(TEXT_COLUMNS) | set(KEY_COLUMNS) | set(COORDINATE_LIMITS) | {"Telehealth_Services"}
    require_columns(raw, required)

    # The deep copy ensures all operations are isolated from the loaded raw frame.
    clean = raw.copy(deep=True)
    clean["__source_row__"] = clean.index
    examples: list[dict[str, Any]] = []

    # 1. Trim and normalize the two requested categorical fields.
    rows_before, nulls_before = len(clean), null_count(clean)
    changed_text_ids: set[Any] = set()
    modified = 0
    for column in TEXT_COLUMNS:
        original = clean[column].copy()
        standardized = original.astype("string").str.strip().str.upper()
        changed = original.notna() & standardized.ne(original.astype("string"))
        modified += int(changed.sum())
        changed_text_ids.update(clean.loc[changed, "__source_row__"].tolist())
        # Retain a small, varied set of examples rather than a large audit payload.
        for row_id in clean.loc[changed, "__source_row__"].head(2):
            old = original.loc[clean["__source_row__"] == row_id].iloc[0]
            new = standardized.loc[clean["__source_row__"] == row_id].iloc[0]
            examples.append({"row": row_id, "field": column, "original": old, "expected": new})
        clean[column] = standardized
    audit_step("Whitespace and casing", rows_before, nulls_before, clean, modified_cells=modified)

    # 2. Coerce coordinates safely, retaining only values inside California's bounds.
    rows_before, nulls_before = len(clean), null_count(clean)
    invalid_coordinate_ids: set[Any] = set()
    modified = 0
    for column, (lower, upper) in COORDINATE_LIMITS.items():
        original = clean[column].copy()
        numeric = pd.to_numeric(original, errors="coerce")
        valid = numeric.between(lower, upper, inclusive="both")
        invalid = original.notna() & ~valid
        modified += int(invalid.sum())
        invalid_coordinate_ids.update(clean.loc[invalid, "__source_row__"].tolist())
        for row_id in clean.loc[invalid, "__source_row__"].head(1):
            old = original.loc[clean["__source_row__"] == row_id].iloc[0]
            examples.append({"row": row_id, "field": column, "original": old, "expected": pd.NA})
        # Invalid, nonnumeric, and out-of-state values all become a true null.
        clean[column] = numeric.where(valid, pd.NA)
    audit_step("California coordinate validation", rows_before, nulls_before, clean, modified_cells=modified)

    # 3. Normalize recognized boolean spellings. Unrecognized populated flags become null
    # rather than being guessed as Y or N.
    rows_before, nulls_before = len(clean), null_count(clean)
    original_flag = clean["Telehealth_Services"].copy()
    normalized_flag = original_flag.astype("string").str.strip().str.upper()
    clean_flag = normalized_flag.map(lambda x: "Y" if x in YES_VALUES else "N" if x in NO_VALUES else pd.NA)
    # A sentinel makes an unexpected populated flag (for example, "UNKNOWN")
    # count as a modification when it is deliberately converted to null.
    changed_flag = original_flag.notna() & (
        clean_flag.fillna("<INVALID_FLAG>").astype("string").ne(original_flag.astype("string"))
    )
    telehealth_ids = set(clean.loc[changed_flag, "__source_row__"].tolist())
    clean["Telehealth_Services"] = clean_flag.astype("string")
    audit_step("Telehealth flag standardization", rows_before, nulls_before, clean, modified_cells=int(changed_flag.sum()))

    # 4. Keep the first occurrence of each provider/location composite key.
    rows_before, nulls_before = len(clean), null_count(clean)
    duplicate_rows = clean.duplicated(subset=list(KEY_COLUMNS), keep="first")
    duplicate_survivor_ids: set[Any] = set()
    for _, group in clean.loc[clean.duplicated(subset=list(KEY_COLUMNS), keep=False)].groupby(list(KEY_COLUMNS), dropna=False):
        duplicate_survivor_ids.add(group.iloc[0]["__source_row__"])
    clean = clean.loc[~duplicate_rows].copy()
    audit_step("Composite-key deduplication", rows_before, nulls_before, clean, rows_dropped=int(duplicate_rows.sum()))

    # Store sampling groups as attributes so the exported data remains free of helper columns.
    clean.attrs["sample_ids"] = {
        "text": changed_text_ids,
        "coordinates": invalid_coordinate_ids,
        "telehealth": telehealth_ids,
        "duplicate_survivors": duplicate_survivor_ids,
    }
    return clean, examples


def select_representative_sample(clean: pd.DataFrame, limit: int = 50) -> pd.DataFrame:
    """Select edge cases first, then fill to *limit* with stable row order.

    A duplicate itself cannot be exported because it was correctly removed.  Its
    retained first record is included instead, proving the duplicate key remains
    represented in the clean sample.
    """
    candidate_ids: list[Any] = []
    groups = clean.attrs.get("sample_ids", {})
    for group_name in ("text", "coordinates", "telehealth", "duplicate_survivors"):
        # Reserve capacity for every kind of edge case.  This prevents the very
        # common text-normalization changes from consuming all 50 sample slots.
        candidate_ids.extend(sorted(groups.get(group_name, set()))[:10])
    # Add ordinary retained rows for a reproducible sample of up to 50 records.
    candidate_ids.extend(clean["__source_row__"].tolist())

    selected: list[Any] = []
    seen: set[Any] = set()
    retained_ids = set(clean["__source_row__"])
    for row_id in candidate_ids:
        if row_id in retained_ids and row_id not in seen:
            selected.append(row_id)
            seen.add(row_id)
        if len(selected) == limit:
            break
    return clean.set_index("__source_row__", drop=True).loc[selected].reset_index(drop=True)


def print_verification_examples(raw: pd.DataFrame, clean: pd.DataFrame, examples: list[dict[str, Any]]) -> None:
    """Print exactly five concrete Original / Expected / Actual checks."""
    print("\nVerification examples (Original Value | Expected Value | Actual Value)")
    lookup = clean.set_index("__source_row__", drop=False)
    chosen = examples[:5]
    # Text casing is present in this extract, but retain a defensive fallback for any schema variant.
    if len(chosen) < 5:
        for row_id in raw.index:
            for column in TEXT_COLUMNS:
                value = raw.at[row_id, column]
                expected = value if pd.isna(value) else str(value).strip().upper()
                chosen.append({"row": row_id, "field": column, "original": value, "expected": expected})
                if len(chosen) == 5:
                    break
            if len(chosen) == 5:
                break
    for number, example in enumerate(chosen, start=1):
        row_id, field = example["row"], example["field"]
        actual = lookup.at[row_id, field] if row_id in lookup.index else "<ROW REMOVED AS DUPLICATE>"
        print(
            f"  {number}. source row {row_id}, {field}: "
            f"{display_value(example['original'])} | {display_value(example['expected'])} | {display_value(actual)}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean medical provider data without changing the raw CSV.")
    parser.add_argument("--input", type=Path, default=Path("medical.csv"), help="raw CSV path (default: medical.csv)")
    parser.add_argument("--output", type=Path, default=Path("cleaned_sample_50.csv"), help="sample CSV path")
    args = parser.parse_args()

    if not args.input.is_file():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    # String dtype preserves IDs (including possible leading zeroes); coordinates are converted explicitly later.
    raw = pd.read_csv(args.input, dtype="string", low_memory=False)
    print(f"Initial dataset dimensions: {len(raw):,} rows x {len(raw.columns):,} columns")
    clean, examples = clean_provider_data(raw)
    print_verification_examples(raw, clean, examples)

    sample = select_representative_sample(clean, limit=50)
    sample.to_csv(args.output, index=False)
    print(f"\nExported {len(sample):,} cleaned representative rows to: {args.output}")
    print(f"Final cleaned dataset dimensions (before sampling): {len(clean):,} rows x {len(clean.columns) - 1:,} columns")


if __name__ == "__main__":
    main()
