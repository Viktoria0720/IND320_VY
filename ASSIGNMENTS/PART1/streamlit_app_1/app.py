# app.py
import streamlit as st

from core.constants import AREAS_DF
from core.ui import SECTIONS
from pages import (
    overview,
    elhub_production,
    elhub_timeseries,
    weather_overview,
    weather_anomalies,
    meta_about,
)
APP_VERSION = "v-2025-11-26-02"  # CHANGE this string every time you want to test

st.sidebar.write("APP VERSION:", APP_VERSION)

# Page config
st.set_page_config(page_title="IND320 • Open-Meteo + Elhub", layout="wide")
st.markdown(
    """
    <style>
    .block-container {max-width: 1400px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# Session defaults
if "area" not in st.session_state:
    st.session_state.area = "NO5"
if "wx2021" not in st.session_state:
    st.session_state.wx2021 = None

# Sidebar navigation
st.sidebar.title("Navigation")
section = st.sidebar.selectbox("Section", list(SECTIONS.keys()), index=0)
page = st.sidebar.radio("Page", SECTIONS[section], index=0)


# Route to page modules
if section == "Overview" and page == "Home":
    overview.render(section)

elif section == "Elhub – Production" and page == "Production Dashboard":
    elhub_production.render(section)

elif section == "Elhub – Production" and page == "Production Time Series":
    elhub_timeseries.render(section)

elif section == "Open-Meteo – Weather" and page == "Weather Overview":
    weather_overview.render(section)

elif section == "Open-Meteo – Weather" and page == "Weather Anomalies":
    weather_anomalies.render(section)

elif section == "Meta" and page == "About":
    meta_about.render(section)
