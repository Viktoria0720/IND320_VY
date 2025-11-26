# pages/overview.py
import streamlit as st
from core.constants import AREAS_DF
from core.ui import section_badge, apply_section_theme

def render(section: str):
    # Apply per-section CSS
    apply_section_theme(section)
    section_badge("Overview", section)
    st.title("Welcome to the IND320 App 🌦️⚡")

    st.write(
        "Use the navigation on the left. "
        "Start with **Elhub – Production → Production Dashboard** to choose a price area."
    )

    st.dataframe(AREAS_DF[["area", "city", "lon", "lat"]], use_container_width=True)
