# pages/price_area_map.py
import json
from datetime import date, timedelta

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

from core.constants import AREAS_DF
from core.ui import section_badge, apply_section_theme
from core.geo_helpers import get_production_groups, mean_production_by_area, _area_to_feature_code

GEOJSON_PATH = "file.geojson"  
GEOJSON_AREA_PROP = "ElSpotOmr"      



@st.cache_data(show_spinner=False)
def load_geojson():
    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)



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

    st.session_state.area = st.selectbox("Chosen price area", area_codes, index=area_codes.index(default_area))
    chosen_area = st.session_state.area

    st.markdown("---")

    # 4) Controls for production/consumption + time interval
    st.subheader("Data selection")

    col1, col2, col3 = st.columns([1.2, 1.2, 2])

    with col1:
        data_type = st.radio(
            "Data type",
            ["Production", "Consumption"],
            help="Consumption requires that you have loaded your consumption data into Mongo / Cassandra.",
        )

    with col2:
        year = st.selectbox("Year", [2021, 2022, 2023, 2024], index=0)

    with col3:
        prod_groups = get_production_groups()
        selected_group = st.selectbox("Energy group", prod_groups)

    c4, c5 = st.columns(2)
    with c4:
        start_date = st.date_input("Start date", date(year, 1, 1))
    with c5:
        days = st.slider("Interval length (days)", 1, 31, 7)

    # Build timestamps
    start_ts = pd.to_datetime(start_date)
    end_ts = start_ts + timedelta(days=int(days))

    st.caption(f"Interval: {start_ts.date()} → {end_ts.date()} (not inclusive)")

    # 5) Compute mean values per area (for now: production only)
    if data_type == "Production":
        mean_df = mean_production_by_area(selected_group, start_ts, end_ts)
    else:
        st.warning("Consumption choropleth not yet wired – using production as placeholder.")
        mean_df = mean_production_by_area(selected_group, start_ts, end_ts)

    # Map internal 'NO1' → GeoJSON 'NO 1'
    mean_df = mean_df.copy()
    mean_df["geo_code"] = mean_df["area"].apply(_area_to_feature_code)

    # 6) Map setup
    st.subheader("Map")

    # Remember last clicked point across reruns
    if "last_clicked" not in st.session_state:
        st.session_state.last_clicked = None

    # Center map roughly on Norway
    m = folium.Map(location=[65.0, 13.0], zoom_start=4, tiles="CartoDB positron")

    # 7) Choropleth coloring of areas (transparent-ish)
    # We map area → mean_value
    if not mean_df.empty:
        choropleth = folium.Choropleth(
            geo_data=geojson_data,
            name="mean_values",
            data=mean_df,
            columns=["geo_code", "mean_value"],   # 👈 use geo_code
            key_on=f"feature.properties.{GEOJSON_AREA_PROP}",  # ElSpotOmr
            fill_color="YlOrRd",
            fill_opacity=0.6,
            line_opacity=0.2,
            highlight=True,
            legend_name=f"Mean {data_type.lower()} ({selected_group})",
        )
        choropleth.add_to(m)


    # 8) Add outline layer with highlight for chosen area
    def style_function(feature):
        code = feature["properties"].get(GEOJSON_AREA_PROP)  # e.g. "NO 1"
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
