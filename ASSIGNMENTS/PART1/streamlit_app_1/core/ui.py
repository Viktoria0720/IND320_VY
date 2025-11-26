# core/ui.py
import streamlit as st
from .constants import AREAS_DF

SECTIONS = {
    "Overview": ["Home"],
    "Elhub – Production": ["Production Dashboard", "Production Time Series"],
    "Open-Meteo – Weather": ["Weather Overview", "Weather Anomalies"],
    "Meta": ["About"],
}

SECTION_COLORS = {
    "Overview": "#2b6777",
    "Elhub – Production": "#6c63ff",
    "Open-Meteo – Weather": "#2e7d32",
    "Meta": "#9c27b0",
}

def section_badge(label: str, section: str):
    color = SECTION_COLORS.get(section, "#444")
    st.markdown(
        f"""
        <div style="
            background:{color};
            color:white;
            padding:0.25rem 0.75rem;
            border-radius:999px;
            display:inline-block;
            font-size:0.8rem;
            margin-bottom:0.5rem;">
            {label}
        </div>
        """,
        unsafe_allow_html=True,
    )
def apply_section_theme(section: str):
    # Pick colors per group
    if section == "Elhub – Production":
        primary = "#0B7285"
        bg = "#E3FAFC"
        sidebar_bg = "#0B7285"
    elif section == "Weather – Overview":
        primary = "#7048E8"
        bg = "#F3F0FF"
        sidebar_bg = "#7048E8"
    else:  # Meta / default
        primary = "#2B8A3E"
        bg = "#EBFBEE"
        sidebar_bg = "#2B8A3E"

    st.markdown(
        f"""
        <style>
        /* App background */
        .stApp {{
            background-color: {bg};
        }}

        /* Sidebar background */
        section[data-testid="stSidebar"] > div {{
            background-color: {sidebar_bg};
        }}

        /* Sidebar text color */
        section[data-testid="stSidebar"] * {{
            color: white;
        }}

        /* Primary buttons */
        .stButton > button {{
            background-color: {primary};
            border-color: {primary};
            color: white;
        }}

        /* Radio / select highlight */
        div[role="radiogroup"] label[data-baseweb="radio"] > div:first-child,
        div[data-baseweb="select"] > div {{
            border-color: {primary};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

apply_section_theme(section)
