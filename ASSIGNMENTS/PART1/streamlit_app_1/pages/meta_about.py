# pages/meta_about.py
import streamlit as st
from core.ui import section_badge, apply_section_theme


def render(section: str):
    section_badge("Meta", section)
    apply_section_theme(section)
    st.title("Keep Calm and Don’t Give Up on Coding 💻")
    st.markdown(
        "<div style='background-color:#245; color:white; font-size:40px; "
        "text-align:center; padding:50px;'>You're almost there! 🚀</div>",
        unsafe_allow_html=True,
    )
