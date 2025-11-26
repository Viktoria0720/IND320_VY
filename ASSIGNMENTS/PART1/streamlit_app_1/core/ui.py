# core/ui.py
import streamlit as st
from .constants import AREAS_DF  # if unused, you can remove this import

SECTIONS = {
    "Overview": ["Home"],
    "Elhub – Production": ["Production Dashboard", "Production Time Series"],
    "Open-Meteo – Weather": ["Weather Overview", "Weather Anomalies"],
    "Meta": ["About"],
}

# Main accent colors per section
SECTION_COLORS = {
    "Overview": "#2b6777",
    "Elhub – Production": "#6c63ff",
    "Open-Meteo – Weather": "#2e7d32",
    "Meta": "#9c27b0",
}

# Backgrounds / “feel” per section
SECTION_THEMES = {
    "Overview": {
        "bg": "linear-gradient(135deg, #e3f2fd 0%, #ffffff 60%)",
        "sidebar_bg": "#1b3c47",
    },
    "Elhub – Production": {
        "bg": "linear-gradient(135deg, #f3e5f5 0%, #ffffff 60%)",
        "sidebar_bg": "#312e81",
    },
    "Open-Meteo – Weather": {
        "bg": "linear-gradient(135deg, #e8f5e9 0%, #ffffff 60%)",
        "sidebar_bg": "#1b5e20",
    },
    "Meta": {
        "bg": "linear-gradient(135deg, #fce4ec 0%, #ffffff 60%)",
        "sidebar_bg": "#4a148c",
    },
}


def apply_section_theme(section: str):
    """
    Injects CSS that tweaks background, sidebar and headings
    based on the active section.
    Call this at the top of each page render().
    """
    accent = SECTION_COLORS.get(section, "#444")
    theme = SECTION_THEMES.get(section, {})
    bg = theme.get("bg", "white")
    sidebar_bg = theme.get("sidebar_bg", "#111")

    st.markdown(
        f"""
        <style>
        /* Page background */
        .stApp {{
            background: {bg};
        }}

        /* Sidebar background */
        [data-testid="stSidebar"] > div:first-child {{
            background: {sidebar_bg};
        }}

        /* Sidebar text */
        [data-testid="stSidebar"] * {{
            color: #f9f9f9 !important;
        }}

        /* Header colors */
        h1, h2, h3 {{
            color: {accent};
        }}

        /* Buttons / sliders accent */
        .stSlider > div[data-baseweb="slider"] > div {{
            background-color: rgba(0,0,0,0.06);
        }}
        .st-emotion-cache-1inwz65 a, .st-emotion-cache-1inwz65 button {{
            border-radius: 999px;
        }}

        /* Radio / select highlight */
        .st-emotion-cache-16idsys a, .st-emotion-cache-16idsys label {{
            color: {accent} !important;
        }}

        </style>
        """,
        unsafe_allow_html=True,
    )


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


def style_plotly(fig, section: str):
    """
    Apply the section accent color to Plotly titles / axes.
    Call this just before st.plotly_chart(fig, ...).
    """
    accent = SECTION_COLORS.get(section, "#444")
    fig.update_layout(
        title_font=dict(color=accent),
        xaxis=dict(title_font=dict(color=accent), tickfont=dict(color="#333")),
        yaxis=dict(title_font=dict(color=accent), tickfont=dict(color="#333")),
        legend=dict(
            title_font=dict(color=accent),
            font=dict(color="#333"),
        ),
        paper_bgcolor="rgba(255,255,255,0.9)",
        plot_bgcolor="rgba(255,255,255,0.85)",
    )
    return fig
