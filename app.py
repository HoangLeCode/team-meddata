"""Medi-Cal FFS Provider Availability Planner."""

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from provider_analysis import dashboard_outputs, load_eligible_data, load_provider_data


ROOT = Path(__file__).parent
PROVIDER_PATH = ROOT / "data" / "clean" / "providers_clean.parquet"
ELIGIBLE_PATH = ROOT / "eligible_clean.csv"
COUNTIES_GEOJSON_PATH = ROOT / "data" / "boundaries" / "ca_counties.geojson"

NAVY = "#103B67"
TEAL = "#168A8C"
GOLD = "#C98516"
MUTED = "#607083"

st.set_page_config(
    page_title="Medi-Cal FFS Provider Availability Planner",
    page_icon="✚",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner="Loading cleaned provider and eligible data...")
def load_inputs():
    providers = load_provider_data(PROVIDER_PATH)
    eligible = load_eligible_data(ELIGIBLE_PATH)
    return providers, eligible


@st.cache_data(show_spinner=False)
def load_county_geojson():
    with COUNTIES_GEOJSON_PATH.open(encoding="utf-8") as boundary_file:
        return json.load(boundary_file)


def pct(value):
    return "N/A" if value is None or pd.isna(value) else f"{value:.2f}%"


def rate(value):
    return "N/A" if value is None or pd.isna(value) else f"{value:.2f}"


def make_rate_map(county_table, county_geojson, selected_county="All counties"):
    """Render county availability as a boundary choropleth, with NA areas neutral."""
    county_ids = pd.DataFrame(
        [
            {
                "CountyName": feature["properties"]["CENSUS_PLACE_NAME"].removesuffix(" County"),
                "geoid": feature["properties"]["CENSUS_GEOID"],
            }
            for feature in county_geojson["features"]
        ]
    )
    mapped = county_ids.merge(county_table, on="CountyName", how="left", validate="one_to_one")
    valid = mapped.dropna(subset=["locations_per_10k"]).copy()
    unavailable = mapped[mapped["locations_per_10k"].isna()].copy()

    if valid.empty:
        figure = go.Figure()
    else:
        value_max = float(valid["locations_per_10k"].quantile(0.95))
        if value_max <= float(valid["locations_per_10k"].min()):
            value_max = float(valid["locations_per_10k"].min()) + max(
                abs(float(valid["locations_per_10k"].min())) * 0.01,
                1.0,
            )
        figure = px.choropleth_map(
            valid,
            geojson=county_geojson,
            locations="geoid",
            featureidkey="properties.CENSUS_GEOID",
            color="locations_per_10k",
            color_continuous_scale="RdYlGn",
            range_color=(float(valid["locations_per_10k"].min()), value_max),
            map_style="white-bg",
            center={"lat": 37.25, "lon": -119.5},
            zoom=4.4,
            opacity=0.88,
            height=455,
        )
        hover_below = valid["below_median"].map({True: "Yes", False: "No"}).fillna("N/A")
        figure.update_traces(
            marker_line_color="white",
            marker_line_width=0.8,
            customdata=pd.DataFrame(
                {
                    "county": valid["CountyName"],
                    "locations": valid["provider_locations"],
                    "eligibles": valid["eligible_count"],
                    "rate": valid["locations_per_10k"],
                    "below": hover_below,
                }
            ).to_numpy(),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Provider locations: %{customdata[1]:,}<br>"
                "Medi-Cal eligibles: %{customdata[2]:,}<br>"
                "Locations per 10,000: %{customdata[3]:.2f}<br>"
                "Below statewide median: %{customdata[4]}<extra></extra>"
            ),
        )

    if not unavailable.empty:
        eligible_display = unavailable["eligible_count"].map(
            lambda value: "unavailable" if pd.isna(value) else f"{int(value):,}"
        )
        missing_customdata = pd.DataFrame(
            {
                "county": unavailable["CountyName"],
                "locations": unavailable["provider_locations"].map(lambda value: f"{int(value):,}"),
                "eligibles": eligible_display,
            }
        ).to_numpy()
        figure.add_trace(
            go.Choroplethmap(
                geojson=county_geojson,
                featureidkey="properties.CENSUS_GEOID",
                locations=unavailable["geoid"],
                z=[0] * len(unavailable),
                colorscale=[[0, "#D8DEE6"], [1, "#D8DEE6"]],
                showscale=False,
                marker={"line": {"color": "white", "width": 0.8}},
                customdata=missing_customdata,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Provider locations: %{customdata[1]}<br>"
                    "Medi-Cal eligibles: %{customdata[2]}<br>"
                    "Locations per 10,000: unavailable<extra></extra>"
                ),
                showlegend=False,
            )
        )

    if selected_county != "All counties":
        selected = mapped[mapped["CountyName"] == selected_county]
        if not selected.empty:
            figure.add_trace(
                go.Choroplethmap(
                    geojson=county_geojson,
                    featureidkey="properties.CENSUS_GEOID",
                    locations=selected["geoid"],
                    z=[1],
                    colorscale=[[0, "rgba(16, 59, 103, 0.12)"], [1, "rgba(16, 59, 103, 0.12)"]],
                    showscale=False,
                    marker={"line": {"color": NAVY, "width": 3}},
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    figure.update_layout(
        map={"center": {"lat": 37.25, "lon": -119.5}, "zoom": 4.4},
        margin=dict(l=0, r=0, t=0, b=0),
        coloraxis_colorbar=dict(title="Locations<br>per 10k", thickness=14, titlefont=dict(color="#1D2B3A"), tickfont=dict(color="#1D2B3A")),
        paper_bgcolor="white",
        font=dict(color="#1D2B3A"),  # <-- Forces dark text on hover/labels
    )
    return figure


def make_comparison_chart(priority, median):
    chart = priority.sort_values("locations_per_10k", ascending=True)

    figure = go.Figure(
        go.Bar(
            x=chart["locations_per_10k"],
            y=chart["CountyName"],
            orientation="h",
            marker_color=TEAL,
            text=chart["locations_per_10k"].map(lambda value: f"{value:.2f}"),
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Locations per 10k: %{x:.2f}<extra></extra>",
        )
    )

    if median is not None:
        figure.add_vline(
            x=median,
            line_dash="dash",
            line_color=NAVY,
            annotation_text=f"Statewide median ({median:.2f})",
            annotation_position="top right",
        )

    figure.update_layout(
        height=315,
        margin=dict(l=0, r=40, t=38, b=5),
        xaxis_title="Provider locations per 10,000 Medi-Cal eligibles",
        yaxis_title=None,
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        font=dict(color="#1D2B3A"),
    )

    figure.update_xaxes(gridcolor="#E8EDF2", zeroline=False, tickfont=dict(color="#1D2B3A"), titlefont=dict(color="#1D2B3A"))
    figure.update_yaxes(tickfont=dict(color="#1D2B3A"))
    return figure


def apply_priority_county_selection():
    selection = st.session_state.get("priority_table")
    rows = selection.selection.rows if selection is not None else []
    county_names = st.session_state.get("priority_county_names", [])
    if rows and rows[0] < len(county_names):
        st.session_state["county_filter"] = county_names[rows[0]]


st.markdown(
    f"""
    <style>
      .stApp {{ background: #F5F7FA; color: #1D2B3A; }}
      
      /* Force readable text colors across widgets and labels */
      label, .stSelectbox label, [data-testid="stWidgetLabel"] p, .stMarkdown p {{
        color: #1D2B3A !important;
      }}
      
      [data-testid="stSidebar"] {{
        background: #FFFFFF;
        border-right: 1px solid #DCE3EA;
      }}
      
      [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {{
        color: #1D2B3A !important;
      }}

      [data-testid="stMetricLabel"] {{
        color: #556070 !important;
      }}

      [data-testid="stMetricValue"] {{
        color: {NAVY} !important;
      }}

      .hero {{
        background: linear-gradient(100deg, {NAVY}, #15517F);
        border-radius: 12px;
        padding: 1.25rem 1.7rem;
        color: white;
        margin-bottom: 1rem;
      }}
      .hero h1 {{
        font-size: 2rem;
        line-height: 1.15;
        margin: 0;
        color: white !important;
      }}
      .hero p {{
        margin: .3rem 0 0;
        color: #D8E7F3 !important;
        font-size: 1.03rem;
      }}
      .eyebrow {{
        color: {NAVY};
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .08em;
        font-size: .78rem;
      }}
      .section-title {{
        color: {NAVY};
        font-size: 1.28rem;
        font-weight: 750;
        margin: .1rem 0 .1rem;
      }}
      .section-copy {{
        color: {MUTED};
        margin: 0 0 .75rem;
      }}
      .notice {{
        background: #FFF7E6;
        border-left: 4px solid {GOLD};
        border-radius: 6px;
        padding: .8rem .95rem;
        color: #5D4610;
        font-size: .9rem;
      }}
      .footer {{
        color: #677585;
        font-size: .78rem;
        border-top: 1px solid #DCE3EA;
        padding-top: .65rem;
        margin-top: .5rem;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

try:
    providers, eligible = load_inputs()

    with st.sidebar:
        st.markdown("<div class='eyebrow'>1 · Filter results</div>", unsafe_allow_html=True)
        st.markdown("### Explore access indicator")

        options = dashboard_outputs(providers, eligible)["filter_options"]

        county = st.selectbox(
            "County",
            options["counties"],
            index=0,
            key="county_filter",
            help="Choose one county to highlight it and show its current result. The statewide median stays fixed.",
        )
        specialty = st.selectbox(
            "Provider specialty",
            options["specialties"],
            index=0,
            help="Specialty results are exploratory because specialty values are incomplete.",
        )

        st.selectbox(
            "Population segment",
            ["All Medi-Cal eligibles"],
            disabled=True,
            help="Fixed to all Medi-Cal eligibles for this version of the dashboard.",
        )

        st.selectbox(
            "Reporting period",
            ["Latest available month"],
            disabled=True,
            help="Fixed to the latest available month in the included eligible-count data.",
        )

        st.markdown(
            "<div class='notice'><b>Specialty is exploratory.</b><br>"
            "Specialty data are incomplete; use it to identify questions for "
            "follow-up, not as a confirmed access measure.</div>",
            unsafe_allow_html=True,
        )

    outputs = dashboard_outputs(
        providers,
        eligible,
        specialty=specialty,
        county=county,
    )

    county_table = outputs["county_table"]
    priority = outputs["priority_counties"]
    st.session_state["priority_county_names"] = priority["CountyName"].tolist()
    quality = outputs["data_quality"]
    median = outputs["statewide_median"]

    st.markdown(
        """
        <div class="hero">
          <h1>Medi-Cal FFS Provider Availability Planner</h1>
          <p>Decision metric: unique FFS provider locations per 10,000 Medi-Cal eligibles</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_columns = st.columns(4)

    metric_values = [
        (
            "Median rate / 10,000",
            rate(median),
            "Median valid county rate for the selected specialty: unique FFS provider locations per 10,000 Medi-Cal eligibles. County selection does not change this benchmark.",
        ),
        (
            "Counties below median",
            outputs["counties_below_median"],
            "Number of counties with a valid rate below the statewide median for the selected specialty.",
        ),
        (
            "County identified (%)",
            pct(quality["county_identified_pct"]),
            "Share of all provider records with a nonblank county value.",
        ),
        (
            "Specialty missing (%)",
            pct(quality["missing_specialty_pct"]),
            "Share of all provider records with a blank specialty value.",
        ),
    ]
    for column, (label, value, help_text) in zip(metric_columns, metric_values):
        with column:
            with st.container(border=True):
                st.metric(label, value, help=help_text)

    left, right = st.columns([1, 1.25], gap="large")

    with left:
        st.markdown(
            "<div class='eyebrow'>2 · Compare relative availability</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div class='section-title'>Provider locations per 10k eligibles</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "<p class='section-copy'>County fill shows calculated provider locations per "
            "10,000 eligibles. Hover for the county count, denominator, rate, and median "
            "comparison. Gray counties have an unavailable rate.</p>",
            unsafe_allow_html=True,
        )

        chart = make_rate_map(
            county_table,
            load_county_geojson(),
            county,
        )

        if chart is None:
            st.info(
                "No counties have both eligible counts and mappable provider "
                "locations for this selection."
            )
        else:
            st.plotly_chart(
                chart,
                width="stretch",
                config={"displayModeBar": False},
            )

    with right:
        st.markdown(
            "<div class='eyebrow'>3 · Identify counties for follow-up</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div class='section-title'>Priority counties for follow-up</div>",
            unsafe_allow_html=True,
        )

        if county != "All counties":
            selected = outputs["selected_county"]

            if not selected.empty:
                row = selected.iloc[0]
                eligible_display = (
                    "unavailable" if pd.isna(row["eligible_count"]) else f"{int(row['eligible_count']):,}"
                )

                below = row["below_median"]
                comparison = "unavailable" if pd.isna(below) else ("below" if below else "at or above")
                st.markdown(
                    f"<div class='notice'><b>Selected county: {county}</b><br>"
                    f"{int(row['provider_locations']):,} provider locations · "
                    f"{eligible_display} Medi-Cal eligibles · "
                    f"<b>{rate(row['locations_per_10k'])}</b> locations per 10,000 · "
                    f"{comparison} the statewide median"
                    "</div>",
                    unsafe_allow_html=True,
                )

        st.markdown(
            "<p class='section-copy'>Lowest valid provider-location rate first. "
            "Select a row to show that county's details and highlight it on the map.</p>",
            unsafe_allow_html=True,
        )

        table = priority[
            [
                "rank",
                "CountyName",
                "provider_locations",
                "eligible_count",
                "locations_per_10k",
                "difference_from_median",
            ]
        ].copy()

        table.columns = [
            "Rank",
            "County",
            "Locations",
            "Eligibles",
            "Rate / 10k",
            "Δ median",
        ]
        table["Locations"] = table["Locations"].map(lambda value: f"{int(value):,}")
        table["Eligibles"] = table["Eligibles"].map(lambda value: f"{int(value):,}")
        table["Rate / 10k"] = table["Rate / 10k"].map(lambda value: f"{value:.2f}")
        table["Δ median"] = table["Δ median"].map(lambda value: f"{value:+.2f}")

        st.caption("Lowest valid rate first. Rate is provider locations per 10,000 eligibles; Δ is county rate minus statewide median.")

        st.dataframe(
            table,
            hide_index=True,
            width="stretch",
            key="priority_table",
            on_select=apply_priority_county_selection,
            selection_mode="single-row",
            column_config={
                "Rank": st.column_config.NumberColumn(width=44, format="%d"),
                "County": st.column_config.TextColumn(width=130),
                "Locations": st.column_config.TextColumn(
                    width=86,
                    help="Unique provider service locations for the county.",
                ),
                "Eligibles": st.column_config.TextColumn(
                    width=88,
                    help="All Medi-Cal eligible residents in the county.",
                ),
                "Rate / 10k": st.column_config.TextColumn(
                    width=82,
                    help="Provider locations per 10,000 eligible residents.",
                ),
                "Δ median": st.column_config.TextColumn(
                    width=84,
                    help="County rate minus the statewide median, in locations per 10,000 eligibles.",
                ),
            },
        )

    st.markdown(
        "<div class='section-title'>Compare counties to statewide median</div>",
        unsafe_allow_html=True,
    )

    st.plotly_chart(
        make_comparison_chart(priority, median),
        width="stretch",
        config={"displayModeBar": False},
    )

    st.markdown(
        """
        <div class="notice">
          <b>Data quality and interpretation:</b> Provider data covers enrolled
          Medi-Cal Fee-for-Service listings only. Specialty values are incomplete,
          so specialty views are exploratory. Low relative availability is a signal
          for human follow-up, not a confirmed provider shortage. The denominator
          includes all Medi-Cal eligibles; it does not describe the managed-care
          network or appointment availability.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="footer">
          <b>Scope:</b> Medi-Cal Fee-for-Service provider listings only. This
          indicator does not measure appointment availability, total provider
          capacity, travel time, language match, whether providers accept new
          patients, or Managed Care access.<br>
          County rates use the latest available eligible-population month.
          County outlines use the California Department of Technology's public
          <a href="https://publish.data.ca.gov/dataset/california-county-boundaries-and-identifiers">county boundary dataset</a>.
        </div>
        """,
        unsafe_allow_html=True,
    )

except Exception as e:
    st.error("⚠️ App crashed during startup:")
    st.exception(e)
    import traceback
    st.code(traceback.format_exc())
