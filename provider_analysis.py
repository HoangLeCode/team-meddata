"""Reusable Phase 2 backend for Team MedData; no dashboard UI.

Dependencies: pandas, pyarrow.
Canonical provider input: data/clean/providers_clean.parquet.
Eligible input: CSV with CountyName, reporting_month, eligible_count (or use
clean_eligible_counts with explicit source-column names). No population is
invented. See BACKEND_README.md for the verified DHCS eligible snapshot.

Example:
    providers = load_provider_data('data/clean/providers_clean.parquet')
    eligible = load_eligible_data('eligible_clean.csv')
    outputs = dashboard_outputs(providers, eligible)

County analysis uses canonical geo_status/ca_county, never raw CountyName alone.
Provider locations are deduplicated for counting ONLY, after specialty filtering.
The canonical enrollment dataset is not deduplicated or overwritten.
"""

import pandas as pd


CA_COUNTIES = (
    'Alameda', 'Alpine', 'Amador', 'Butte', 'Calaveras', 'Colusa',
    'Contra Costa', 'Del Norte', 'El Dorado', 'Fresno', 'Glenn', 'Humboldt',
    'Imperial', 'Inyo', 'Kern', 'Kings', 'Lake', 'Lassen', 'Los Angeles',
    'Madera', 'Marin', 'Mariposa', 'Mendocino', 'Merced', 'Modoc', 'Mono',
    'Monterey', 'Napa', 'Nevada', 'Orange', 'Placer', 'Plumas', 'Riverside',
    'Sacramento', 'San Benito', 'San Bernardino', 'San Diego', 'San Francisco',
    'San Joaquin', 'San Luis Obispo', 'San Mateo', 'Santa Barbara',
    'Santa Clara', 'Santa Cruz', 'Shasta', 'Sierra', 'Siskiyou', 'Solano',
    'Sonoma', 'Stanislaus', 'Sutter', 'Tehama', 'Trinity', 'Tulare',
    'Tuolumne', 'Ventura', 'Yolo', 'Yuba',
)


def require_columns(frame, columns):
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f'Missing required columns: {missing}')


def standardize_counties(values):
    """Normalize labels for the California county join; unknowns stay visible."""
    labels = values.astype('string').str.strip().str.replace(r'\s+', ' ', regex=True)
    labels = labels.str.replace(r'(?i)\s+county$', '', regex=True)
    labels = labels.replace('', pd.NA).str.casefold()
    labels = labels.replace('los ángeles', 'los angeles')
    lookup = {name.casefold(): name for name in CA_COUNTIES}
    # Unrecognized labels are retained so clean_eligible_counts can report them.
    return labels.map(lambda name: lookup.get(name, name) if pd.notna(name) else pd.NA).astype('string')


def load_provider_data(path='data/clean/providers_clean.parquet'):
    """Load the team's canonical output, preserving codes and nullable types."""
    providers = pd.read_parquet(path)
    require_columns(providers, [
        'Provider_Number', 'Service_Location_Number', 'CountyName',
        'FI_Provider_Specialty', 'specialty_status', 'geo_status',
        'ca_county', 'ca_county_fips', 'Latitude', 'Longitude',
    ])
    return providers


def clean_eligible_counts(raw, county_col='CountyName',
                          month_col='reporting_month', count_col='eligible_count'):
    """Return standardized county-month totals without assuming raw row scope.

    Input MUST already be one total-All-Medi-Cal-eligibles row per county/month.
    Do not feed age/sex/program breakdowns or sum mixed subtotals. Duplicate
    county-month keys raise an error instead of selecting or summing a row.
    Blank counts stay unavailable; nonnumeric, negative or infinite counts fail.
    Reporting months must be unambiguous dates such as 2026-09 or 2026-09-01.
    Unrecognized/missing county labels fail with their original labels reported.
    """
    require_columns(raw, [county_col, month_col, count_col])
    result = raw[[county_col, month_col, count_col]].copy()
    result.columns = ['CountyName', 'reporting_month', 'eligible_count']
    original_counties = result['CountyName'].copy()
    result['CountyName'] = standardize_counties(result['CountyName'])
    invalid_counties = ~result['CountyName'].isin(CA_COUNTIES)
    if invalid_counties.any():
        raise ValueError('Unrecognized eligible county labels: ' +
                         str(original_counties[invalid_counties].unique().tolist()))
    dates = pd.to_datetime(result['reporting_month'], format='mixed', errors='coerce')
    if dates.isna().any():
        raise ValueError('Missing or invalid reporting_month; supply unambiguous dates.')
    result['reporting_month'] = dates.dt.to_period('M').dt.to_timestamp()
    text_counts = result['eligible_count'].astype('string').str.strip()
    text_counts = text_counts.str.replace(',', '', regex=False).replace('', pd.NA)
    counts = pd.to_numeric(text_counts, errors='coerce')
    invalid = text_counts.notna() & counts.isna()
    if invalid.any():
        raise ValueError('Nonnumeric eligible counts: ' + str(text_counts[invalid].unique().tolist()))
    if (counts.lt(0) | counts.isin([float('inf'), -float('inf')])).any():
        raise ValueError('Eligible counts must be finite and nonnegative.')
    if counts.dropna().mod(1).ne(0).any():
        raise ValueError('Eligible counts must be whole people.')
    result['eligible_count'] = counts.astype('Int64')
    if result.duplicated(['CountyName', 'reporting_month']).any():
        raise ValueError('Duplicate county-month totals; resolve population scope before analysis.')
    return result.sort_values(['reporting_month', 'CountyName']).reset_index(drop=True)


# Official DHCS resource reached from the California Open Data dataset page.
ELIGIBLE_SOURCE_URL = (
    'https://data.chhs.ca.gov/dataset/8c897320-ba87-4574-bc37-bae974191c35/'
    'resource/9ade93e4-0676-4117-adbe-a53378d7fe84/download/'
    't6_eligibility_by_medicare_dual_status_201001_sept2026.csv'
)


def prepare_dhcs_eligible_counts(raw):
    """Extract the latest county totals from the DHCS dual-status resource.

    Dual and Non-Dual are mutually exclusive Medi-Cal enrollment categories.
    For each of 58 counties require exactly one of each, with no suppressed
    values. Their sum is All Medi-Cal eligibles, not the FFS-only population.
    Exclude the STATEWIDE summary from county rows, then use it as a check.
    Source Status and Date of Data are retained in the returned audit.
    """
    require_columns(raw, ['Month of Eligibility', 'County', 'Dual Status',
                          'Total Eligibles', 'Annotation Code',
                          'Annotation Description', 'Status', 'Date of Data'])
    data = raw.copy()
    months = pd.to_datetime(data['Month of Eligibility'], format='%Y-%m', errors='raise')
    if months.isna().any() or data.empty:
        raise ValueError('Missing eligibility month or empty source.')
    latest_month = months.max()
    data = data[months == latest_month].copy()
    statewide = data[(data['County'] == 'STATEWIDE') & (data['Dual Status'] == 'STATEWIDE')]
    if len(statewide) != 1:
        raise ValueError('Expected exactly one latest-month statewide total.')
    county_rows = data.drop(statewide.index).copy()
    county_rows['County'] = standardize_counties(county_rows['County'])
    if set(county_rows['County']) != set(CA_COUNTIES):
        raise ValueError('Latest DHCS snapshot does not contain exactly 58 valid California counties.')
    if not county_rows['Dual Status'].isin(['Dual', 'Non-Dual']).all():
        raise ValueError('Unexpected dual-status category.')
    if county_rows.duplicated(['County', 'Dual Status']).any():
        raise ValueError('Duplicate county/dual-status records.')
    if not county_rows.groupby('County').size().eq(2).all():
        raise ValueError('Every county needs both Dual and Non-Dual records.')
    notes = county_rows['Annotation Code'].fillna('').astype('string').str.strip()
    descriptions = county_rows['Annotation Description'].fillna('').astype('string').str.strip()
    if notes.ne('').any() or descriptions.ne('').any():
        raise ValueError('Annotated/suppressed county counts require review; do not sum partial data.')
    counts = pd.to_numeric(county_rows['Total Eligibles'].astype('string').str.replace(',', '', regex=False), errors='raise')
    if counts.isna().any() or counts.lt(0).any() or counts.mod(1).ne(0).any():
        raise ValueError('Missing or invalid county eligible counts.')
    county_rows['eligible_count'] = counts.astype('int64')
    result = county_rows.groupby('County', as_index=False)['eligible_count'].sum()
    result = result.rename(columns={'County': 'CountyName'})
    result['reporting_month'] = latest_month
    result = clean_eligible_counts(result)
    statewide_count = pd.to_numeric(str(statewide['Total Eligibles'].iloc[0]).replace(',', ''), errors='raise')
    if int(result['eligible_count'].sum()) != int(statewide_count):
        raise ValueError('County eligible totals do not reconcile to the source statewide total.')
    audit = {
        'source_url': ELIGIBLE_SOURCE_URL,
        'reporting_month': latest_month.strftime('%Y-%m'),
        'source_date_of_data': sorted(data['Date of Data'].dropna().unique().tolist()),
        'source_status': sorted(data['Status'].dropna().unique().tolist()),
        'county_count': len(result),
        'county_component_records': len(county_rows),
        'statewide_eligible_count': int(statewide_count),
        'population_scope': 'All Medi-Cal certified eligibles: Dual + Non-Dual',
        'provider_snapshot_date': None,
        'provider_snapshot_note': 'Not recorded in the supplied canonical Parquet; do not infer from enrollment effective dates.',
    }
    return result, audit


def load_eligible_data(path='eligible_clean.csv'):
    """Load standardized totals or the named DHCS raw resource."""
    raw = pd.read_csv(path, dtype='string', keep_default_na=False)
    if 'Month of Eligibility' in raw.columns:
        return prepare_dhcs_eligible_counts(raw)[0]
    return clean_eligible_counts(raw)


def latest_eligible_counts(eligible):
    """Use ONE latest reporting month across counties; do not mix months."""
    eligible = clean_eligible_counts(eligible)
    if eligible.empty:
        raise ValueError('Eligible data is empty.')
    latest = eligible['reporting_month'].max()
    return eligible[eligible['reporting_month'] == latest].reset_index(drop=True)


def california_records(providers, specialty=None):
    require_columns(providers, ['geo_status', 'ca_county', 'specialty_status',
                                'FI_Provider_Specialty'])
    selected = providers[providers['geo_status'] == 'california']
    if specialty is not None and specialty != 'All specialties':
        selected = selected[
            (selected['specialty_status'] == 'specified') &
            (selected['FI_Provider_Specialty'] == specialty)
        ]
    return selected.copy()


def filter_options(providers, eligible=None):
    ca = california_records(providers)
    if eligible is None:
        counties = sorted(ca['ca_county'].dropna().unique().tolist())
    else:
        counties = sorted(latest_eligible_counts(eligible)['CountyName'].tolist())
    specialties = ca.loc[ca['specialty_status'] == 'specified', 'FI_Provider_Specialty']
    specialties = specialties.dropna().astype('string').str.strip()
    specialties = specialties[~specialties.str.upper().isin(['', 'NOT APPLICABLE', 'N/A', 'UNKNOWN'])]
    return {'counties': ['All counties'] + counties,
            'specialties': ['All specialties'] + sorted(specialties.unique().tolist())}


def provider_location_counts(providers, specialty=None):
    """Count distinct provider-location-county combinations, not providers/rows."""
    require_columns(providers, ['Provider_Number', 'Service_Location_Number'])
    selected = california_records(providers, specialty)
    keys = ['Provider_Number', 'Service_Location_Number', 'ca_county']
    locations = selected.dropna(subset=keys).copy()
    # Empty string IDs are also excluded, without changing identifiers' types.
    valid_ids = (locations['Provider_Number'].astype('string').str.strip().ne('') &
                 locations['Service_Location_Number'].astype('string').str.strip().ne(''))
    locations = locations[valid_ids].drop_duplicates(keys)
    result = locations.groupby('ca_county').size().reset_index(name='provider_locations')
    return result.rename(columns={'ca_county': 'CountyName'}).sort_values('CountyName').reset_index(drop=True)


def data_quality(providers):
    """Fixed full-dataset metrics, unaffected by county/specialty filters.

    county_identified_pct follows BUILD_SPEC: raw CountyName nonblank share;
    california_county_pct separately reports canonical CA geography coverage.
    missing_specialty_pct counts null cleaned specialty labels; in canonical
    data these represent all non-specified statuses. It is NOT merely the
    specialty_status='missing' share, which is returned separately.
    """
    require_columns(providers, ['CountyName', 'FI_Provider_Specialty',
                                'specialty_status', 'geo_status'])
    total = len(providers)
    county_known = providers['CountyName'].astype('string').str.strip().replace('', pd.NA).notna()
    specialty_missing = providers['FI_Provider_Specialty'].astype('string').str.strip().replace('', pd.NA).isna()
    def percentage(mask):
        return 100 * int(mask.sum()) / total if total else None
    return {
        'enrollment_records': total,
        'county_identified_pct': percentage(county_known),
        'missing_specialty_pct': percentage(specialty_missing),
        'california_county_pct': percentage(providers['geo_status'] == 'california'),
        'specialty_status_missing_pct': percentage(providers['specialty_status'] == 'missing'),
        'geo_status_counts': providers['geo_status'].value_counts(dropna=False).to_dict(),
        'specialty_status_counts': providers['specialty_status'].value_counts(dropna=False).to_dict(),
    }


def county_analysis(providers, eligible, specialty=None):
    """Return shared chart/map/ranking data, statewide metrics and join reports.

    Eligible latest-month counties form the base. Missing CA counties in that
    source and provider counties unmatched to it are explicitly reported.
    An outer completeness check uses the fixed 58 CA names, not observed rows.
    Rates are unrounded for ranking/median. Zero providers is a valid zero rate
    when the denominator is positive. Missing/zero denominators yield NA.
    Median is the unweighted median of valid county rates for this specialty.
    """
    latest = latest_eligible_counts(eligible)
    counts = provider_location_counts(providers, specialty)
    table = latest.merge(counts, on='CountyName', how='left', validate='one_to_one')
    table['provider_locations'] = table['provider_locations'].fillna(0).astype('int64')
    denominator = table['eligible_count'].where(table['eligible_count'] > 0)
    table['locations_per_10k'] = table['provider_locations'] / denominator * 10000
    valid_rates = table['locations_per_10k'].dropna()
    rate_median = valid_rates.median() if not valid_rates.empty else None
    median = float(rate_median) if pd.notna(rate_median) else None
    table['difference_from_median'] = table['locations_per_10k'] - (median if median is not None else float('nan'))
    table['below_median'] = table['locations_per_10k'].lt(median) if median is not None else pd.Series(pd.NA, index=table.index, dtype='boolean')
    table = table.sort_values('CountyName').reset_index(drop=True)
    priority = table.dropna(subset=['locations_per_10k']).sort_values(
        ['locations_per_10k', 'CountyName']).head(5).reset_index(drop=True)
    priority.insert(0, 'rank', range(1, len(priority) + 1))
    all_provider_counties = provider_location_counts(providers)['CountyName']
    missing_names = sorted(set(CA_COUNTIES) - set(latest['CountyName']))
    unmatched = sorted(set(all_provider_counties) - set(latest['CountyName']))
    # Include absent counties in unavailable report, without adding them to the base table.
    unavailable = pd.DataFrame({'CountyName': list(CA_COUNTIES)}).merge(
        latest, on='CountyName', how='left', validate='one_to_one', indicator=True)
    unavailable['reason'] = pd.Series(pd.NA, index=unavailable.index, dtype='string')
    unavailable.loc[unavailable['_merge'] == 'left_only', 'reason'] = 'absent_from_latest_month'
    unavailable.loc[(unavailable['_merge'] == 'both') & unavailable['eligible_count'].isna(), 'reason'] = 'missing_eligible_count'
    unavailable.loc[unavailable['eligible_count'].eq(0).fillna(False), 'reason'] = 'zero_eligible_count'
    unavailable = unavailable[unavailable['reason'].notna()].drop(columns='_merge').reset_index(drop=True)
    return {
        'county_table': table,
        'statewide_median': median,
        'counties_below_median': int(table['below_median'].fillna(False).sum()),
        'priority_counties': priority,
        'unavailable_counties': unavailable,
        'missing_eligible_counties': missing_names,
        'unmatched_provider_counties': unmatched,
        'reporting_month': latest['reporting_month'].max(),
    }


def specialty_summary(providers, county=None):
    """Supplementary specialty counts and record-based excluded share."""
    selected = california_records(providers)
    if county is not None and county != 'All counties':
        selected = selected[selected['ca_county'] == county]
    specified = selected[selected['specialty_status'] == 'specified']
    result = specified.groupby('FI_Provider_Specialty')['Provider_Number'].nunique().reset_index(name='provider_count')
    result = result.sort_values(['provider_count', 'FI_Provider_Specialty'], ascending=[False, True]).reset_index(drop=True)
    total = len(selected)
    return result, {
        'total_enrollment_records': total,
        'excluded_enrollment_records': total - len(specified),
        'excluded_record_share': (total - len(specified)) / total if total else None,
    }


def dashboard_outputs(providers, eligible, specialty=None, county=None):
    """Return all MVP backend outputs; county selection never changes benchmark."""
    # Validate selections before calculating; a typo must not create zero rates.
    options = filter_options(providers, eligible)
    if specialty is not None and specialty not in options['specialties']:
        raise ValueError(f'Unknown specialty: {specialty}')
    if county is not None and county not in options['counties']:
        raise ValueError(f'Unknown county: {county}')
    outputs = county_analysis(providers, eligible, specialty)
    selected = california_records(providers, specialty)
    if county is not None and county != 'All counties':
        selected = selected[selected['ca_county'] == county]
        selection = outputs['county_table'][outputs['county_table']['CountyName'] == county].copy()
    else:
        selection = outputs['county_table'].copy()
    outputs.update({
        'provider_records': providers.copy(),
        'eligible_counts': latest_eligible_counts(eligible),
        'filter_options': options,
        'data_quality': data_quality(providers),
        'provider_location_counts': provider_location_counts(providers, specialty),
        'selected_county': selection.reset_index(drop=True),
        'selected_provider_records': selected.reset_index(drop=True),
        'specialty_coverage': specialty_summary(providers, county)[1],
    })
    return outputs


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Preview backend calculations without a dashboard.')
    parser.add_argument('--providers', default='data/clean/providers_clean.parquet')
    parser.add_argument('--eligible', default='eligible_clean.csv',
                        help='Standardized eligible totals or the official DHCS dual-status CSV.')
    parser.add_argument('--prepare-eligible', help='Convert the DHCS raw CSV into eligible_clean.csv and an audit, then exit.')
    parser.add_argument('--county', default='All counties')
    parser.add_argument('--specialty', default='All specialties')
    args = parser.parse_args()
    if args.prepare_eligible:
        import json
        raw = pd.read_csv(args.prepare_eligible, dtype='string', keep_default_na=False)
        eligible, audit = prepare_dhcs_eligible_counts(raw)
        import hashlib
        from pathlib import Path
        audit['source_sha256'] = hashlib.sha256(Path(args.prepare_eligible).read_bytes()).hexdigest()
        eligible.to_csv('eligible_clean.csv', index=False)
        with open('eligible_source_audit.json', 'w') as stream:
            json.dump(audit, stream, indent=2)
        print('Prepared eligible_clean.csv and eligible_source_audit.json')
        raise SystemExit(0)
    providers = load_provider_data(args.providers)
    from pathlib import Path
    if Path(args.eligible).is_file():
        eligible = load_eligible_data(args.eligible)
        result = dashboard_outputs(providers, eligible, args.specialty, args.county)
        print(result['county_table'].to_string(index=False))
        print('\nPriority counties:\n', result['priority_counties'].to_string(index=False))
        print('\nStatewide median:', result['statewide_median'])
        print('\nUnavailable counties:\n', result['unavailable_counties'].to_string(index=False))
        print('\nUnmatched provider counties:', result['unmatched_provider_counties'])
    else:
        print(provider_location_counts(providers, args.specialty).to_string(index=False))
        print('\nEligible file not supplied: rates and priorities have NOT been calculated.')
    print('\nFixed data quality:', data_quality(providers))
