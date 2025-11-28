# pages/price_area_map.py
import json
from pathlib import Path
from datetime import date, timedelta

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
import plotly.express as px
import numpy as np

from core.constants import AREAS_DF
from core.ui import section_badge, apply_section_theme, style_plotly
from core.geo_helpers import get_energy_groups, mean_energy_by_area
from core.elhub_energy import load_area_energy_series

# Folder of THIS file (pages/price_area_map.py)
HERE = Path(__file__).resolve().parent

# If file.geojson lives next to app.py one level up from pages/
GEOJSON_PATH = HERE.parent / "file.geojson"
GEOJSON_AREA_PROP = "ElSpotOmr"


@st.cache_data(show_spinner=False)
def load_geojson():
    try:
        with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"GeoJSON file not found at {GEOJSON_PATH}")
        raise


def _area_to_feature_code(area_code: str) -> str:
    """
    Convert internal code 'NO1' to the GeoJSON code 'NO 1', etc.
    """
    area_code = area_code.strip().upper()
    if area_code.startswith("NO") and len(area_code) == 3:
        return f"NO {area_code[-1]}"
    return area_code


def render(section: str):
    # 1) Apply section theme + header
    apply_section_theme(section)
    section_badge("Maps", section)
    st.title("Price Area Map – Production / Consumption Overview")
    # 2) Load GeoJSON
    try:
        geojson_data = load_geojson()
    except FileNotFoundError:
        st.error(f"GeoJSON file not found at `{GEOJSON_PATH}`.")
        st.info("Download the NVE Elspot areas as GeoJSON and save it to that path.")
        return

    # 3) Global area selection (we reuse the same area as other pages)
    area_codes = AREAS_DF["area"].tolist()
    default_area = st.session_state.get("area", "NO5")
    if default_area not in area_codes:
        default_area = area_codes[0]

    st.session_state.area = st.selectbox(
        "Chosen price area",
        area_codes,
        index=area_codes.index(default_area),
    )
    chosen_area = st.session_state.area

    st.markdown("---")

    # 4) Controls for production/consumption + time interval
    st.subheader("Data selection")

    col1, col2, col3 = st.columns([1.2, 1.2, 2])

    # Production vs Consumption
    with col1:
        data_type = st.radio(
            "Data type",
            ["Production", "Consumption"],
            help="Consumption requires that you have loaded your consumption data into Mongo / Cassandra.",
        )

    # Year for convenient default date
    with col2:
        year = st.selectbox("Year", [2021, 2022, 2023, 2024], index=0)

    # Group depends on Production/Consumption
    with col3:
        energy_groups = get_energy_groups(data_type)
        selected_group = st.selectbox("Energy group", energy_groups)

    # Time interval (in days)
    c4, c5 = st.columns(2)
    with c4:
        start_date = st.date_input("Start date", date(year, 1, 1))
    with c5:
        days = st.slider("Interval length (days)", 1, 31, 7)

    # Build timestamps (naive Oslo time, handled in helpers)
    start_ts = pd.to_datetime(start_date)
    end_ts = start_ts + timedelta(days=int(days))

    st.caption(f"Interval: {start_ts.date()} → {end_ts.date()} (not inclusive)")

    # 5) Compute mean values per area for the selected data type + group + interval
    try:
        with st.spinner("Computing mean energy per price area from Mongo …"):
            mean_df = mean_energy_by_area(
                data_type=data_type,
                group=selected_group,
                start=start_ts,
                end=end_ts,
            )
    except Exception as e:
        st.error("Could not compute mean energy per area (Mongo issue?).")
        with st.expander("Details"):
            st.exception(e)
        return

    # Ensure numeric and handle zeros (no-data) separately so the choropleth shows transparent areas
    mean_df = mean_df.copy()
    mean_df["mean_value"] = pd.to_numeric(mean_df.get("mean_value", 0.0), errors="coerce").fillna(0.0)

    # Attach mean values to GeoJSON features so tooltips can display the numeric mean
    geo_mean_map = {row["area"]: float(row["mean_value"]) for _, row in mean_df.iterrows()}
    for feat in geojson_data.get("features", []):
        code = feat.get("properties", {}).get(GEOJSON_AREA_PROP)
        if code is None:
            feat["properties"]["mean_value"] = None
            continue
        # area codes in mean_df use e.g. 'NO1' -> convert feature code 'NO 1' to 'NO1' for lookup
        lookup_code = code.replace(" ", "")
        feat["properties"]["mean_value"] = geo_mean_map.get(lookup_code, None)

    # Map internal 'NO1' → GeoJSON 'NO 1'
    mean_df = mean_df.copy()
    mean_df["geo_code"] = mean_df["area"].apply(_area_to_feature_code)

    # 6) Map setup
    st.subheader("Map")

    # Style function used by GeoJson layers (defined before we create layers)
    def style_function(feature):
        code = feature.get("properties", {}).get(GEOJSON_AREA_PROP)  # e.g. "NO 1"
        chosen_code = _area_to_feature_code(chosen_area)     # "NO1" → "NO 1"

        if code == chosen_code:
            return {
                "fillOpacity": 0.0,
                "color": "#000000",
                "weight": 3,
            }
        else:
            return {
                "fillOpacity": 0.0,
                "color": "#444444",
                "weight": 1,
            }

    # Remember last clicked point across reruns
    if "last_clicked" not in st.session_state:
        st.session_state.last_clicked = None

    # Center map roughly on Norway
    m = folium.Map(location=[65.0, 13.0], zoom_start=4, tiles="CartoDB positron")

    # 7) Choropleth coloring of areas (transparent-ish)
    # We map area → mean_value
    if not mean_df.empty:
        # Prepare a colour scale based on non-zero means (quantiles)
        vals = mean_df["mean_value"].replace(0, np.nan).dropna()
        threshold_scale = None
        if not vals.empty:
            try:
                qs = np.quantile(vals, [0.0, 0.25, 0.5, 0.75, 1.0])
                # Ensure monotonic unique thresholds for folium
                threshold_scale = sorted(list({float(x) for x in qs}))
            except Exception:
                threshold_scale = None

        choropleth = folium.Choropleth(
            geo_data=geojson_data,
            name="mean_values",
            data=mean_df,
            columns=["geo_code", "mean_value"],
            key_on=f"feature.properties.{GEOJSON_AREA_PROP}",
            fill_color="YlOrRd",
            threshold_scale=threshold_scale,
            fill_opacity=0.65,
            line_opacity=0.2,
            highlight=True,
            legend_name=f"Mean {data_type.lower()} ({selected_group})",
        )
        choropleth.add_to(m)

        # Add a GeoJson layer with tooltips that include the mean value
        def _fmt_mean(mv):
            return f"{mv:,.1f} kWh" if mv is not None and not pd.isna(mv) else "No data"

        folium.GeoJson(
            geojson_data,
            name="labels",
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=[GEOJSON_AREA_PROP, "mean_value"],
                aliases=["Area:", f"Mean {data_type} (kWh):"],
                localize=True,
                labels=True,
                sticky=False,
                toLocaleString=False,
            ),
            highlight_function=lambda x: {"weight": 3, "color": "#666"},
        ).add_to(m)

    # 8) Add outline layer with highlight for chosen area
    folium.GeoJson(
        geojson_data,
        name="outlines",
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(fields=[GEOJSON_AREA_PROP], aliases=["Area:"]),
    ).add_to(m)

    # 9) Add marker for last clicked coordinate (if any)
    if st.session_state.last_clicked is not None:
        lat = st.session_state.last_clicked["lat"]
        lng = st.session_state.last_clicked["lng"]
        folium.CircleMarker(
            location=[lat, lng],
            radius=5,
            color="red",
            fill=True,
            fill_opacity=0.9,
            popup=f"Clicked: {lat:.4f}, {lng:.4f}",
        ).add_to(m)

    # 10) Render map with click capture
    map_data = st_folium(m, height=600, width="stretch")

    # --- Energy stats for the selected area and time period ---
    st.subheader("Energy in selected area")
    try:
        with st.spinner("Loading energy data for the chosen area …"):
            energy_df = load_area_energy_series(
                energy_type=data_type,         # "Production" / "Consumption"
                area=chosen_area,              # from your area selectbox
                group=selected_group,          # from "Energy group" selectbox
                start_ts=start_ts,
                end_ts=end_ts,
            )
    except Exception as e:
        st.error("Could not load energy data for the chosen area.")
        with st.expander("Details"):
            st.exception(e)
        return
    
    if energy_df.empty:
        st.info(
            "No energy data found for this combination "
            f"({data_type}, {selected_group}, {chosen_area}, {start_ts.date()}–{end_ts.date()})."
        )
    else:
        total_kwh = float(energy_df["kwh"].sum())
        mean_kwh = float(energy_df["kwh"].mean())
        n_hours = int(energy_df.shape[0])

        c1, c2, c3 = st.columns(3)
        c1.metric("Total energy (kWh)", f"{total_kwh:,.0f}")
        c2.metric("Mean per hour (kWh)", f"{mean_kwh:,.1f}")
        c3.metric("Hours with data", f"{n_hours:,}")

        # Time series plot for the selected area and group
        fig = px.line(
            energy_df,
            x="time",
            y="kwh",
            title=f"{data_type} – {selected_group} in {chosen_area}",
            labels={"time": "Time", "kwh": "kWh"},
        )
        fig = style_plotly(fig, section)
        st.plotly_chart(fig, width="stretch")

    # 11) Store clicked coordinate in session and show it
    last_clicked = map_data.get("last_clicked") if map_data else None
    if last_clicked is not None:
        st.session_state.last_clicked = last_clicked

    with st.expander("Clicked coordinate", expanded=True):
        if st.session_state.last_clicked is None:
            st.write("Click anywhere on the map to store a coordinate.")
        else:
            lat = st.session_state.last_clicked["lat"]
            lng = st.session_state.last_clicked["lng"]
            st.write(f"Last clicked: **lat = {lat:.5f}**, **lon = {lng:.5f}**")

    # 12) Show mean values as a small table too
    st.subheader("Area summary")
    st.dataframe(mean_df, width="stretch")
