# core/ui.py
import streamlit as st

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

SECTION_THEMES = {
    "Overview": {
        "bg": "linear-gradient(135deg, #e3f2fd 0%, #ffffff 60%)",
        "sidebar_bg": "#146783",
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
    """Inject CSS to theme the main view + sidebar."""
    accent = SECTION_COLORS.get(section, "#444")
    theme = SECTION_THEMES.get(section, {})
    bg = theme.get("bg", "white")
    sidebar_bg = theme.get("sidebar_bg", "#111")

    st.markdown(
        f"""
        <style>
        /* MAIN APP BACKGROUND */
        [data-testid="stAppViewContainer"] {{
            background: {bg};
        }}

        /* SIDEBAR BACKGROUND */
        [data-testid="stSidebar"] > div:first-child {{
            background: {sidebar_bg};
        }}

        /* SIDEBAR TEXT COLOR */
        [data-testid="stSidebar"] * {{
            color: #f9f9f9 !important;
        }}

        /* HEADERS */
        h1, h2, h3 {{
            color: {accent} !important;
        }}

        /* LINKS / STRONG TEXT */
        a, .stMarkdown strong {{
            color: {accent};
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
    """Apply section accent color to Plotly charts."""
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
