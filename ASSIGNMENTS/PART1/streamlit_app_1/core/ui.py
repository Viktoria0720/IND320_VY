# core/ui.py
import streamlit as st

SECTIONS = {
    "Overview": ["Home"],
    "Elhub – Production": ["Production Dashboard", "Production Time Series"],
    "Maps": ["Price Area Map"], 
    "Open-Meteo – Weather": ["Weather Overview", "Weather Anomalies"],
    "Meta": ["About"],
}

# Accent colors (badges, titles, plot accents)
SECTION_COLORS = {
    "Overview": "#2b6777",
    "Elhub – Production": "#ae7be9",   
    "Open-Meteo – Weather": "#d5e44f",
    "Maps": "#5f9462",
    "Meta": "#9c27b0",
}

# Background / sidebar themes
SECTION_THEMES = {
    "Overview": {
        "bg": "linear-gradient(135deg, #e3f2fd 0%, #ffffff 60%)",
        "sidebar_bg": "#146783",
    },
    "Elhub – Production": {
        
        "bg": "linear-gradient(135deg, #f2d9fa 0%, #ffffff 60%)",
        "sidebar_bg": "#710392",
    },
    "Open-Meteo – Weather": {
        "bg": "linear-gradient(135deg, #FAEDD2 0%, #ffffff 60%)",
        "sidebar_bg": "#CAAE10",
    },
    "Maps": {
        "bg": "linear-gradient(135deg, #e8f5e9 0%, #ffffff 60%)",
        "sidebar_bg": "#074d0c",
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
            background: {bg} !important;
        }}

        /* SIDEBAR BACKGROUND */
        [data-testid="stSidebar"] {{
            background: {sidebar_bg} !important;
        }}

        /* SIDEBAR TEXT COLOR */
        [data-testid="stSidebar"] * {{
            color: #999999 !important;
        }}

        /* HEADERS */
        h1, h2, h3 {{
            color: {accent} !important;
        }}

        /* LINKS / STRONG TEXT */
        a, .stMarkdown strong {{
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
    """Apply section accent color to Plotly charts + transparent background."""
    accent = SECTION_COLORS.get(section, "#444")
    fig.update_layout(
        title_font=dict(color=accent),
        xaxis=dict(
            title_font=dict(color=accent),
            tickfont=dict(color="#333"),
        ),
        yaxis=dict(
            title_font=dict(color=accent),
            tickfont=dict(color="#333"),
        ),
        legend=dict(
            title_font=dict(color=accent),
            font=dict(color="#333"),
        ),
        # 🔑 remove the white box:
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig

