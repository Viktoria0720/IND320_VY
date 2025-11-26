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
