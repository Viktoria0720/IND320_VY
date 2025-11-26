# pages/weather_anomalies.py
import streamlit as st
from core.analytics import spc_outliers_temperature, lof_precip_anomalies
from core.ui import section_badge, apply_section_theme, style_plotly


def render(section: str):
    area = st.session_state.get("area", "NO5")
    apply_section_theme(section)
    section_badge("Open-Meteo – Weather", section)
    st.title(f"Weather Anomalies (SPC & LOF) — {area}")

    wx = st.session_state.get("wx2021")
    if wx is None or wx.empty:
        st.info("Go to **Elhub – Production → Production Dashboard** to download weather for 2021 first.")
        return

    tab1, tab2 = st.tabs(["Outlier / SPC (Temperature)", "Anomaly / LOF (Precipitation)"])

    with tab1:
        st.subheader("SPC via DCT (SATV)")
        c1, c2 = st.columns(2)
        dct_cutoff = c1.slider("DCT cutoff (fraction)", 0.0, 0.2, 0.02, 0.005)
        n_sigma = c2.slider("Sigma multiplier", 1.0, 6.0, 3.5, 0.1)
        fig, out_df, summary_df = spc_outliers_temperature(
            wx,
            dct_cutoff=float(dct_cutoff),
            n_sigma=float(n_sigma),
        )
        fig = style_plotly(fig, section)
        st.plotly_chart(fig, width="stretch")
        st.write("Summary:", summary_df)
        st.write("Outlier samples:", out_df.head(50))

    with tab2:
        st.subheader("LOF anomalies (precipitation)")
        c1, c2 = st.columns(2)
        contamination = c1.slider("Expected outlier proportion", 0.001, 0.1, 0.01, 0.001)
        n_neighbors = c2.slider("LOF neighbors", 10, 80, 35, 1)
        fig, anoms_df, summary_df = lof_precip_anomalies(
            wx,
            contamination=float(contamination),
            n_neighbors=int(n_neighbors),
        )
        fig = style_plotly(fig, section)
        st.plotly_chart(fig, width="stretch")
        st.write("Summary:", summary_df)
        st.write("Anomaly samples:", anoms_df.head(50))
