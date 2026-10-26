"""Medi-Cal FFS Provider Availability Planner."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from provider_analysis import dashboard_outputs, load_eligible_data, load_provider_data


ROOT = Path(__file__).parent
PROVIDER_PATH = ROOT / "data" / "clean" / "providers_clean.parquet"
ELIGIBLE_PATH = ROOT / "eligible_clean.csv"

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
def county_centroids(providers: pd.DataFrame) -> pd.DataFrame:
    points = providers.loc[
        (providers["geo_status"] == "california")
        & providers["Latitude"].notna()
        & providers["Longitude"].notna(),
        ["ca_county", "Latitude", "Longitude"],
    ].copy()

    return (
        points.groupby("ca_county", as_index=False)[["Latitude", "Longitude"]]
        .median()
        .rename(
            columns={
                "ca_county": "CountyName",
                "Latitude": "latitude",
                "Longitude": "longitude",
            }
        )
    )


def pct(value):
    return "N/A" if value is None or pd.isna(value) else f"{value:.2f}%"


def rate(value):
    return "N/A" if value is None or pd.isna(value) else f"{value:.2f}"


def make_rate_map(county_table, centroids, selected_county="All counties"):
    mapped = county_table.merge(centroids, on="CountyName", how="left")
    mapped = mapped.dropna(subset=["latitude", "longitude", "locations_per_10k"])

    if mapped.empty:
        return None

    mapped["hover"] = mapped.apply(
        lambda row: (
            f"<b>{row['CountyName']}</b><br>"
            f"Provider locations: {int(row['provider_locations']):,}<br>"
            f"Medi-Cal eligibles: {int(row['eligible_count']):,}<br>"
            f"Locations per 10k: {row['locations_per_10k']:.2f}<br>"
            f"Below statewide median: {'Yes' if row['below_median'] else 'No'}"
        ),
        axis=1,
    )

    figure = px.scatter_mapbox(
        mapped,
        lat="latitude",
        lon="longitude",
        color="locations_per_10k",
        size="provider_locations",
        size_max=28,
        color_continuous_scale="RdYlGn",
        range_color=[
            mapped["locations_per_10k"].min(),
            mapped["locations_per_10k"].quantile(0.95),
        ],
        hover_name="CountyName",
        hover_data={
            "latitude": False,
            "longitude": False,
            "provider_locations": ":,",
            "eligible_count": ":,",
        },
        zoom=4.65,
        center={"lat": 37.15, "lon": -119.55},
        height=455,
    )

    figure.update_traces(
        hovertemplate="%{customdata[0]}<extra></extra>",
        customdata=mapped[["hover"]],
    )

    figure.update_layout(
        mapbox_style="open-street-map",
        margin=dict(l=0, r=0, t=0, b=0),
        coloraxis_colorbar=dict(title="Locations<br>per 10k", thickness=14),
    )

    if selected_county != "All counties":
        focus = mapped[mapped["CountyName"] == selected_county]

        if not focus.empty:
            figure.add_trace(
                go.Scattermapbox(
                    lat=focus["latitude"],
                    lon=focus["longitude"],
                    mode="markers",
                    marker={"size": 34, "color": "rgba(16, 59, 103, 0.22)"},
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

            figure.update_layout(
                mapbox={
                    "center": {
                        "lat": float(focus.iloc[0]["latitude"]),
                        "lon": float(focus.iloc[0]["longitude"]),
                    },
                    "zoom": 6.2,
                }
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
    )

    figure.update_xaxes(gridcolor="#E8EDF2", zeroline=False)
    return figure


st.markdown(
    f"""
    <style>
      .stApp {{ background: #F5F7FA; color: #1D2B3A; }}
      [data-testid="stSidebar"] {{
        background: #FFFFFF;
        border-right: 1px solid #DCE3EA;
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
        color: white;
      }}
      .hero p {{
        margin: .3rem 0 0;
        color: #D8E7F3;
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
except Exception as error:
    st.error("The dashboard could not load its data files.")
    st.exception(error)
    st.stop()

with st.sidebar:
    st.markdown("<div class='eyebrow'>1 · Filter results</div>", unsafe_allow_html=True)
    st.markdown("### Explore access indicator")

    options = dashboard_outputs(providers, eligible)["filter_options"]

    county = st.selectbox("County", options["counties"], index=0)
    specialty = st.selectbox("Provider specialty", options["specialties"], index=0)

    st.selectbox(
        "Population segment",
        ["All Medi-Cal eligibles"],
        disabled=True,
    )

    st.selectbox(
        "Reporting period",
        ["Latest available month"],
        disabled=True,
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

metric_columns[0].metric(
    "Statewide median locations per 10k eligibles",
    rate(median),
)

metric_columns[1].metric(
    "Counties below statewide median",
    outputs["counties_below_median"],
)

metric_columns[2].metric(
    "Provider records with county identified",
    pct(quality["county_identified_pct"]),
)

metric_columns[3].metric(
    "Provider records missing specialty",
    pct(quality["missing_specialty_pct"]),
)

left, right = st.columns([1.56, 1], gap="large")

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
        "<p class='section-copy'>Circle size represents recorded provider "
        "locations. Hover over a county for its rate, eligible population, "
        "and median comparison.</p>",
        unsafe_allow_html=True,
    )

    chart = make_rate_map(
        county_table,
        county_centroids(providers),
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
            use_container_width=True,
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

            st.markdown(
                f"<div class='notice'><b>Selected county: {county}</b><br>"
                f"{int(row['provider_locations']):,} provider locations · "
                f"{int(row['eligible_count']):,} Medi-Cal eligibles · "
                f"<b>{rate(row['locations_per_10k'])}</b> locations per 10k"
                "</div>",
                unsafe_allow_html=True,
            )

    st.markdown(
        "<p class='section-copy'>Lowest valid provider-location rate first. "
        "Selecting a county highlights it on the map and shows its details "
        "above.</p>",
        unsafe_allow_html=True,
    )

    table = priority[
        [
            "rank",
            "CountyName",
            "provider_locations",
            "eligible_count",
            "locations_per_10k",
        ]
    ].copy()

    table.columns = [
        "Rank",
        "County",
        "Provider locations",
        "Medi-Cal eligibles",
        "Locations per 10k",
    ]

    st.dataframe(
        table,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Locations per 10k": st.column_config.NumberColumn(format="%.2f"),
            "Provider locations": st.column_config.NumberColumn(format="%d"),
            "Medi-Cal eligibles": st.column_config.NumberColumn(format="%d"),
        },
    )

st.markdown(
    "<div class='section-title'>Compare counties to statewide median</div>",
    unsafe_allow_html=True,
)

st.plotly_chart(
    make_comparison_chart(priority, median),
    use_container_width=True,
    config={"displayModeBar": False},
)

st.markdown(
    """
    <div class="footer">
      <b>Scope:</b> Medi-Cal Fee-for-Service provider listings only. This
      indicator does not measure appointment availability, total provider
      capacity, travel time, language match, whether providers accept new
      patients, or Managed Care access.<br>
      County rates use the latest available eligible-population month. Low
      availability is an apparent gap for human follow-up, not a confirmed
      provider shortage.
    </div>
    """,
    unsafe_allow_html=True,
)