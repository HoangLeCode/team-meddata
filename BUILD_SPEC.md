# Medi-Cal FFS Provider Availability Planner

## 1. Current vision

A workforce-planning director at the California Department of Health Care Services (DHCS) must decide which California counties should receive further investigation for possible Medi-Cal provider-recruitment support.

The dashboard improves the current process by combining enrolled fee-for-service provider locations with county-level Medi-Cal eligible counts. This allows counties to be compared using provider availability relative to potential need instead of relying only on total provider counts.

The dashboard identifies apparent provider-availability gaps for human follow-up. It does not confirm provider shortages because the data does not measure appointment availability, provider capacity, travel time, whether providers accept new patients, or the complete managed-care network.

## 2. Core use cases

### Use case 1: Identify priority counties

**User selects/inputs:** A provider specialty or keeps “All specialties.”

**Dashboard shows:** A California map, statewide summary metrics, and counties ranked by provider service locations per 10,000 Medi-Cal eligible residents.

**User decides:** Which counties should receive further investigation for possible recruitment support.

### Use case 2: Examine a county

**User selects/inputs:** A county using the dropdown, map, or priority table.

**Dashboard shows:** The county’s provider locations, Medi-Cal eligible count, provider locations per 10,000 eligibles, and comparison with the statewide median.

**User decides:** Whether the county’s apparent provider-availability gap justifies closer review.

### Use case 3: Explore a specialty

**User selects/inputs:** A provider specialty.

**Dashboard shows:** Updated county rates, map colors, priority rankings, and a warning about incomplete specialty data.

**User decides:** Which counties may require specialty-specific investigation and whether the available specialty data is reliable enough to use.

## 3. Starting view

The dashboard opens with:

- County: `All counties`
- Provider specialty: `All specialties`
- Eligible population: `All Medi-Cal eligibles`
- Reporting period: latest available month

The starting view displays:

- Statewide median provider locations per 10,000 eligibles
- Number of counties below the statewide median
- Percentage of provider records with county identified
- Percentage of provider records missing specialty
- California county map
- Five counties with the lowest valid rates
- Bar chart comparing those counties with the statewide median
- Data-quality and scope warnings

All displayed analytical values must be calculated from the loaded data. Phase 1 illustrative values must not be hard-coded.

## 4. Dashboard sections and features

### Filter panel

The filter panel contains county and provider-specialty controls.

Selecting a specialty updates the provider counts, county rates, map, ranking, and comparison chart.

Selecting a county highlights or displays that county’s results without changing the statewide benchmark.

For the MVP, eligible population is fixed at all Medi-Cal eligibles and reporting period is fixed at the latest available month. Additional population and time filters should only be added if the cleaned auxiliary data supports them reliably.

### Summary metrics

The dashboard displays four metric cards:

1. Statewide median provider locations per 10,000 eligibles
2. Number of counties below the statewide median
3. Percentage of provider records with county identified
4. Percentage of provider records missing specialty

The first two metrics respond to the specialty selection. The two data-quality percentages describe the full cleaned provider dataset and remain fixed when filters change.

### California map

The map colors counties by provider service locations per 10,000 eligible residents.

Hovering over a county shows:

- County name
- Unique provider service locations
- Medi-Cal eligible count
- Provider locations per 10,000 eligibles
- Whether the county is below the statewide median

Counties with unavailable eligible-count data appear in a neutral color rather than being shown as zero.

### Priority-county table

The table displays the five counties with the lowest valid provider-location rates.

It includes:

- Rank
- County
- Provider service locations
- Medi-Cal eligible count
- Provider locations per 10,000 eligibles
- Difference from the statewide median

The table is sorted from the lowest rate to the highest rate.

### County comparison chart

A horizontal bar chart displays the five priority counties and their provider-location rates. A vertical reference line represents the statewide median.

This chart helps the user compare the apparent provider gap across the priority counties.

### Data-quality notice

The dashboard explains that:

- The provider data covers enrolled Medi-Cal fee-for-service providers.
- The results do not represent the complete managed-care network.
- Low availability is an apparent gap, not a confirmed shortage.
- Specialty analysis is exploratory because many specialty values are missing or recorded as `NOT APPLICABLE`.

## 5. Metrics and visuals

| Metric or visual | Question answered | Source data and columns | Calculation or aggregation | Relevant filters |
|---|---|---|---|---|
| Unique provider service locations | How many distinct FFS provider locations are recorded in each county? | Provider data: `Provider_Number`, `Service_Location_Number`, `CountyName` | Remove duplicate provider-number, service-location-number, and county combinations; then count by county | County and specialty |
| Locations per 10,000 eligibles | How large is provider supply relative to potential need? | Provider-location counts plus county-level `eligible_count` | `provider_locations / eligible_count * 10000` | Specialty |
| Statewide median | What is the typical county provider-location rate? | County-level `locations_per_10k` | Median of valid county rates | Specialty |
| Counties below median | How many counties fall below the statewide benchmark? | County rates and statewide median | Count counties where rate is below the median | Specialty |
| County identified percentage | How complete is provider geography? | Provider data: `CountyName` | Nonmissing county records divided by all provider records, multiplied by 100 | None |
| Missing specialty percentage | How complete is specialty data? | Provider data: `FI_Provider_Specialty` | Missing specialty records divided by all provider records, multiplied by 100 | None |
| California map | Where is relative provider availability lowest? | `CountyName` and county-level rate | Color each county by `locations_per_10k` | Specialty |
| Priority table | Which counties have the lowest valid rates? | County-level analysis table | Sort rate ascending and keep the first five counties | Specialty |
| Comparison chart | How do priority counties compare with the statewide median? | Priority table and statewide median | Plot county rates with a median reference line | Specialty |

## 6. Data definitions and cleaning decisions

### Provider data

Required provider columns are:

- `Provider_Number`
- `Service_Location_Number`
- `CountyName`
- `FI_Provider_Specialty`
- `Latitude`
- `Longitude`

One source row is a provider-profile record, not necessarily one unique provider or one unique location.

A unique provider service location is defined by:

- `Provider_Number`
- `Service_Location_Number`
- `CountyName`

Repeated combinations of these fields are counted once.

Records missing provider number, service-location number, or county are excluded from provider-location counts.

When a specialty is selected, the data is filtered to that specialty before provider locations are deduplicated.

Blank and `NOT APPLICABLE` specialty values are not offered as specialty filter choices. Valid provider locations with these values remain included in the `All specialties` result.

### Eligible-count data

The auxiliary data must provide:

- County
- Reporting month
- Total Medi-Cal eligible residents

The latest available month is used for the MVP.

County labels must be standardized before joining the datasets. The cleaning code must document how the original fields are converted to:

- `CountyName`
- `reporting_month`
- `eligible_count`

The eligible-count data provides the base list of counties. A county with valid eligible data but no recorded provider location receives a provider count of zero. A county with a missing or zero eligible count receives an unavailable rate, not zero or infinity.

The cleaning decisions in the code, cleaned team data, and this specification must agree.

### Official DHCS Eligible Population Source

The county-level Medi-Cal eligible population data comes from the California Department of Health Care Services (DHCS), *Medi-Cal Certified Eligibles Data by Month with Demographics*.

**Dataset page:**

https://data.ca.gov/@california-department-of-health-care-services/medi-cal-certified-eligibles-data-by-month-with-demographics

**CSV download:**

https://data.chhs.ca.gov/dataset/8c897320-ba87-4574-bc37-bae974191c35/resource/9ade93e4-0676-4117-adbe-a53378d7fe84/download/t6_eligibility_by_medicare_dual_status_201001_sept2026.csv

**Resource:** By Medicare Dual Status, Certified Eligibles

**Reporting month:** September 2026

### Eligible Population Calculation

For each California county, the September 2026 certified eligible counts are aggregated across the Medicare Dual and Non-Dual categories.

The total eligible population is calculated as:

`eligible_count = Dual certified eligibles + Non-Dual certified eligibles`

The provider availability rate is then calculated as:

`locations_per_10k = (provider_locations / eligible_count) * 10000`

County names are standardized before joining the eligible population data with the cleaned provider dataset. According to the team's data preparation results, all 58 California county names match.

Counties with missing or zero eligible counts must have an unavailable provider availability rate rather than a zero or infinite value.

**Important data limitation:** The provider dataset snapshot date still needs to be confirmed. Until verified, the dashboard must clearly disclose that the provider and eligible population datasets may represent different reporting periods.
## 7. Required backend outputs

The Phase 2 backend must return reusable values or DataFrames that provide:

- Cleaned provider records
- Cleaned county-level eligible counts
- Valid county and specialty filter options
- Provider service-location counts by county
- Provider locations per 10,000 eligibles by county
- Statewide median
- Number of counties below the median
- County and specialty data-quality percentages
- Five priority counties
- Counties with unavailable eligible-count data

Backend functions may print results while being tested, but their main outputs must be returned for reuse by the Phase 3 dashboard.

The backend must not include the Streamlit dashboard interface.

## 8. Architecture and technical design

The project separates:

1. Data loading
2. Provider-data cleaning
3. Eligible-data cleaning
4. County-name standardization
5. Filter application
6. Metric calculation
7. Aggregated dashboard outputs
8. Phase 3 presentation code

Each component has one clear job and returns data to the next component. The map, priority table, and comparison chart use the same county-level analysis table rather than calculating the provider rate separately.

Changing one visual should not require changes to data cleaning or unrelated metrics.

The analysis will use:

- `pandas` for loading, cleaning, filtering, joining, and aggregation
- CSV files as raw local inputs
- One canonical cleaning pipeline on the main branch
- A cleaned analysis-ready DataFrame or local processed file
- Streamlit for the Phase 3 interface
- A map/chart library compatible with Streamlit for Phase 3 visuals

Raw downloaded data remains outside Git through `.gitignore`. The repository includes instructions for obtaining the source files and supplying their local paths.

The data is processed once before the dashboard outputs are created. The Phase 3 application may cache the cleaned data so filters do not repeatedly reload and clean the full source files.

## 9. Important interactions

- Selecting a specialty updates the summary metrics, map, priority table, and comparison chart.
- Selecting a county displays that county’s results.
- Selecting a county does not change the statewide median.
- Hovering over a county displays the county’s calculated values.
- Resetting filters restores `All counties` and `All specialties`.
- Missing eligible-count data displays as unavailable rather than zero.
- `NOT APPLICABLE` is not shown as a selectable specialty.

## 10. Build order

1. Reconcile the team’s Module 6 cleaning work.
2. Create one canonical provider-cleaning solution on the main branch.
3. Clean and standardize the eligible-count data.
4. Confirm the unit of analysis and duplicate-handling rule.
5. Standardize county names and test the data join.
6. Calculate provider service locations by county.
7. Calculate provider locations per 10,000 eligibles.
8. Calculate statewide metrics and data-quality measures.
9. Produce the priority-county and chart-ready DataFrames.
10. Add filter-supporting analysis.
11. Test the returned values and edge cases.
12. Run the fresh-agent test and resolve remaining ambiguities.

## 11. Acceptance checks

The Phase 2 work is complete when:

1. Repeated provider-service-location-county combinations are counted once.
2. A provider with two different service locations can contribute two locations.
3. Provider and eligible-count data join correctly using standardized county names.
4. Unmatched county names are reported instead of silently removed.
5. A manually checked county produces the correct locations-per-10,000 rate.
6. Missing or zero eligible counts produce an unavailable rate, not zero or infinity.
7. The priority table contains the five lowest valid county rates in ascending order.
8. Selecting a specialty changes the appropriate aggregated results.
9. The county filter does not change the statewide benchmark.
10. Every major analysis component returns a reusable value or DataFrame.
11. The backend results agree with the definitions in this specification.
12. No illustrative Phase 1 values are hard-coded into the analysis.

## 12. Fresh-agent test

Give a fresh coding agent the repository and this file with the following instruction:

> Read `BUILD_SPEC.md` and inspect the repository. Before implementing or evaluating the backend analysis, list every place where you would need to ask a question, make an assumption, or guess about the product, source data, cleaning rules, calculations, filters, file locations, or expected outputs.

Record each question or guess.

Update this specification, the cleaning documentation, or the repository instructions to resolve every important gap. Repeat the check until a fresh agent can understand the data definitions, calculations, expected outputs, and dashboard behavior without making a major unsupported assumption.

## 13. Team Repository

GitHub Repository:
https://github.com/HoangLeCode/team-meddata