# Cleaning Decisions (Phase 2, Deliverable 2)

One canonical dataset, produced by one script from one raw snapshot.

```
python clean_provider_data.py     # medical.csv -> data/clean/providers_clean.parquet (+ cleaning_audit.json)
pytest test_clean_provider_data.py
```

| | |
|---|---|
| Raw snapshot | `medical.csv`, 372,778 rows x 46 columns, SHA-256 `5294e7c7…8a29b` (checked by the script) |
| Output | `data/clean/providers_clean.parquet`: 372,778 rows x 50 columns (`OBJECTID` dropped, 5 derived columns added) |
| Unit of analysis | **One row = one enrollment record** (provider x service location x provider type/specialty). It is not a provider. |

## 1. Why the teammates' versions could not simply be merged

All five cleanings were checked against the same raw file. Counts below are from that check.

| # | Topic | Who did what | Problem found | **Canonical decision** |
|---|---|---|---|---|
| 1 | **Snapshot** | Ziheng and Xixi: 374,831 rows. Hoang, Eeshita, Angana: 372,778 rows. | Different downloads (DHCS refreshes monthly), so every count differed between teammates. | One agreed file, pinned by hash. The script warns if the hash differs. |
| 2 | **Duplicates** | Hoang and Xixi: keep first row per `Provider_Number + Service_Location_Number` (drops 44,730 rows). Eeshita, Ziheng, Angana: keep all. | Repeated keys are mostly the **same provider with different specialties or types**. Keep-first deletes 17,228 of 125,664 California provider-county-specialty combinations (13.7%), in 55 of 58 counties (Lassen loses 29%). No exact duplicates exist. | **Drop nothing.** "Providers" is a counting rule (distinct `Provider_Number`), not a row filter. Statewide, 360,870 California rows are 293,021 distinct providers (rows overstate by 23%; Los Angeles 93,414 rows vs 78,481 providers). |
| 3 | **Missing specialty** | Xixi: fill "Unknown", then drop Unknown and NOT APPLICABLE rows (keeps 30% of rows). Hoang: uppercase only. Others: ignore. | Specialty is absent for different reasons, and pandas' default reader silently turns the literal `N/A` into NaN (88,998 rows), so teammates' "missing" counts blurred two different situations. Filling "Unknown" invents a category; dropping rows removes most providers and all coverage information. | Keep every row. Add `specialty_status`: `specified` 134,669, `not_applicable` 87,849 (types with no specialty concept, e.g. pharmacies), `not_recorded` 88,998 (literal `N/A`, all from `Provider_Source` 2 and 3), `missing` 61,262. Specialty label is null unless `specified`. **Only 36% of rows have a usable specialty** (project-start.md's "41% missing" understates this). |
| 4 | **(0, 0) coordinates** | Ziheng, Hoang: set to null. Angana: counted only. Eeshita, Xixi: left in place. | 2,457 rows are exactly (0, 0) and all have no county, no state and no ZIP: a "not geocoded" sentinel that would plot at Null Island. | Set to null. |
| 5 | **Coordinate range check** | Hoang: keep only lat 32.5-42, lon -124.5 to -114.1 on all rows. Eeshita: world range. | Hoang's California box wrongly nulls **5,677 valid** out-of-state coordinates (NV, AZ, OR, etc.). | Null only (0, 0) or impossible values (world range). Real out-of-state coordinates stay. |
| 6 | **County labels** | Hoang: UPPER. Eeshita: Title Case. Others: as is. | Case changes break joins to DHCS/Census files and Title Case mangles non-CA labels ("Baltimore city" to "City", "DuPage" to "Dupage"). The only real CA label error is `Los Ángeles` (1 row). | Keep source case. Fix `Los Ángeles` to `Los Angeles County`. |
| 7 | **What counts as California** | Ziheng: `State == "CA"`. Others: group by `CountyName`. | `State == "CA"` yields **65** county names, not 58. Six rows say CA but are in Utah, Idaho, Florida, Illinois, Michigan, New York. Conversely 84 out-of-state rows share a California county's name (Orange County FL, Kings County NY, Lake County OR/IL/IN...), so grouping by name alone mislabels them. | `geo_status` = `california` only when `State == "CA"` **and** the county is one of the 58: 360,870 rows. `out_of_state` 9,451. `unassigned` 2,457 (no county). `state_conflict` flags the 6 mislabeled rows. `ca_county` / `ca_county_fips` are set only for California rows. |
| 8 | **Code columns** | Eeshita converted to numbers and saved. Others kept as text. | Eeshita's CSV has `FI_Provider_Type_CD` 026 -> `26.0`, `FIPS_County_CD` 06037 -> `6037.0`, `DHCS_County_CD` 07 -> `7`, `ZIP_4`/phone as floats. Leading zeros are lost, so codes no longer join. | All identifiers and codes are strings (`Provider_Number` includes alphanumeric `MSS…` IDs; ZIP, ZIP_4, FIPS, codes keep zeros). Stored as Parquet so types cannot drift in a CSV round trip. |
| 9 | **Placeholders** | Mostly untouched. | `-` (141,183 license cells), `No Taxonomy Provided`, `Taxonomy not applicable`, `Unknown` provider type (15,100), `.`/`0` in address fields, literal `N/A`. | Converted to null (counts in `cleaning_audit.json`). Not filled with "Unknown". |
| 10 | **Whitespace** | Angana: `City` only. Eeshita: all text. | Leading/trailing/double spaces in `Legal_Name`, `Address*`, `City`, `Provider_License`. | Trim and collapse spaces in every text column; blank to null. |
| 11 | **Dates** | All parse to datetime. | Two export formats exist (`2011-01-19 0:00:00` here, `1/19/2011` in the other pull). Range 1966-01-01 to 2026-09-04; no failures. | Both formats accepted; anything else raises an error instead of silently nulling. |
| 12 | **Flags** | Xixi: fill "Unknown". | Telehealth, Medicaid/CHIP, accessibility fields are 99.4% null (only 2,107 rows answered). | `Y`/`N` to nullable boolean; null stays null. |

## 2. Rules the dashboard and backend must follow

1. **Count providers with `Provider_Number.nunique()`**, never `len(rows)`. Say "enrollment records" when counting rows.
2. **Specialty analyses filter to `specialty_status == "specified"`** and show the excluded share (64% of rows) next to the result.
3. **Counties come from `ca_county` / `ca_county_fips`** where `geo_status == "california"`. Never group by raw `CountyName` or `State` alone.
4. The 2,457 `unassigned` rows (0.7%) have no location; report them as excluded, do not assign them.
5. We derive FIPS from county name rather than trusting `FIPS_County_CD`: the source uses a statewide placeholder `06000` on 87,307 California rows and disagrees with the location-based county on 274 of the remaining 273,561.

## 3. Derived columns

| Column | Meaning |
|---|---|
| `specialty_status` | `specified` / `not_applicable` / `not_recorded` / `missing` |
| `geo_status` | `california` / `out_of_state` / `unassigned` |
| `state_conflict` | `State == CA` but county is not a California county (6 rows) |
| `ca_county` | County name without "County" (58 values), California rows only |
| `ca_county_fips` | 5-digit FIPS (`06001`..`06115`), California rows only |

## 4. Open items for the team

- **`Provider_Source` 2 and 3** (26,744 and 62,254 rows) have no specialty and no taxonomy. They appear to be a different record class (possibly the NMP/ORP providers DHCS added to the list), but this is unverified. They are kept and can be filtered by `Provider_Source`.
- **FFS only.** The data excludes Managed Care providers and records no capacity or patient demand, so counts measure enrollment, not access.
- **Committing data.** The repo `.gitignore` blocks data files; we added a narrow exception for the two cleaned output files only (17.8 MB). Raw `medical.csv` stays ignored. Confirm this is acceptable for the deliverable.
