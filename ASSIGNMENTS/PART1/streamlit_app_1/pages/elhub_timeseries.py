# pages/elhub_timeseries.py
import streamlit as st
from core.constants import AREAS_DF
from core.mongo_elhub import elhub_available_years, load_elhub_for_area
from core.analytics import stl_decompose_production, production_spectrogram
from core.ui import section_badge, apply_section_theme, style_plotly


def render(section: str):
    section_badge("Elhub – Production", section)
    apply_section_theme(section)
    st.title("Production Time Series – STL & Spectrogram")

    area_codes = AREAS_DF["area"].tolist()
    default_idx = area_codes.index(st.session_state.area) if "area" in st.session_state and st.session_state.area in area_codes else 0
    sel_area = st.selectbox("Area", area_codes, index=default_idx)
    st.session_state.area = sel_area
    area = sel_area

    years = elhub_available_years(area)
    if not years:
        st.error(f"No production data found for {area}.")
        return

    default_year = 2021 if 2021 in years else years[-1]
    year = st.selectbox("Year", years, index=years.index(default_year))

    with st.spinner(f"Loading Elhub production for {area} in {year} …"):
        prod_df = load_elhub_for_area(area, year)

    if prod_df.empty:
        st.warning(f"No production data for {area} in {year}. Try another year.")
        return

    groups = sorted(prod_df["group"].dropna().unique().tolist())
    default_group = groups[0] if groups else "Hydro"

    tab1, tab2 = st.tabs(["STL", "Spectrogram"])

    with tab1:
        st.subheader("STL decomposition")
        c1, c2, c3, c4 = st.columns(4)
        group = c1.selectbox("Production group", options=groups, index=groups.index(default_group))
        period = c2.number_input("Period (season length)", 1, 24*14, 24)
        seasonal = c3.slider("Seasonal smoother", 7, 61, 13, step=2)
        trend = c4.slider("Trend smoother", 21, 401, 101, step=2)
        robust = st.checkbox("Robust", value=True)

        fig, _ = stl_decompose_production(
            prod_df, area=area, group=group,
            period=int(period), seasonal=int(seasonal),
            trend=int(trend), robust=robust
        )
        fig = style_plotly(fig, section)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Spectrogram")
        c1, c2 = st.columns(2)
        group2 = c1.selectbox("Production group", options=groups,
                              index=groups.index(default_group), key="spec_group")
        window_len = c2.number_input("Window length (samples)", 24, 24*30, 24*7, step=24)
        overlap = st.slider("Window overlap", 0.0, 0.9, 0.5, 0.05)

        fig = production_spectrogram(
            prod_df, area=area, group=group2,
            window_len=int(window_len), overlap=float(overlap)
        )
        fig = style_plotly(fig, section)
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("Data info"):
        st.write(f"Area: **{area}**  •  Year: **{year}**  •  Rows: **{len(prod_df):,}**")
        st.dataframe(prod_df.head(), use_container_width=True)
