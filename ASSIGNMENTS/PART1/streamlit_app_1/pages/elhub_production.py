# pages/elhub_production.py
import streamlit as st
import pandas as pd

try:
    import altair as alt
    USE_ALTAIR = True
except Exception:
    alt = None
    USE_ALTAIR = False

try:
    import plotly.express as px
except Exception:
    px = None

from core.constants import AREAS_DF, DASHBOARD_YEAR
from core.open_meteo import get_era5_hourly
from core.mongo_elhub import (
    _get_mongo_collection,
    totals_for_area_year,
    list_groups,
    list_months_for_year,
    monthly_series,
)
from core.ui import section_badge, apply_section_theme, style_plotly


def render(section: str):
    apply_section_theme(section)
    section_badge("Elhub – Production", section)
    st.title("Production Dashboard (Elhub + Open-Meteo)")

    area_codes = AREAS_DF["area"].tolist()
    default_idx = area_codes.index(st.session_state.area) if "area" in st.session_state and st.session_state.area in area_codes else 0
    area = st.radio("Price area", area_codes, index=default_idx, horizontal=True)
    st.session_state.area = area

    # Weather download for the selected area (2021)
    row = AREAS_DF[AREAS_DF["area"] == area].iloc[0]
    with st.spinner(f"Downloading ERA5 hourly weather for {row.city} (2021) from Open-Meteo..."):
        wx = get_era5_hourly(row.lat, row.lon, 2021)
    st.session_state.wx2021 = wx
    st.success(f"Downloaded {len(wx)} rows for {row.city} / {area} (2021).")

    st.divider()
    st.subheader("Elhub – Production overview (MongoDB)")
    try:
        _ = _get_mongo_collection().estimated_document_count()
    except Exception as e:
        st.error("Could not connect to MongoDB.")
        with st.expander("Technical details"):
            st.exception(e)
        return

    left, right = st.columns(2, gap="large")

    with left:
        st.markdown("**Distribution by Production Group (2021)**")
        pie_df = totals_for_area_year(area, DASHBOARD_YEAR)
        if pie_df.empty:
            st.info("No 2021 data for the selected area.")
        else:
            if USE_ALTAIR and alt is not None:
                chart = (
                    alt.Chart(pie_df)
                    .mark_arc()
                    .encode(
                        theta="quantityKwh:Q",
                        color=alt.Color("productionGroup:N", legend=alt.Legend(title="Group")),
                        tooltip=[
                            alt.Tooltip("productionGroup:N", title="Group"),
                            alt.Tooltip("quantityKwh:Q", title="kWh", format=",.0f"),
                        ],
                    )
                    .properties(height=360)
                )
                st.altair_chart(chart, use_container_width=True)
            elif px is not None:
                fig = px.pie(pie_df, names="productionGroup", values="quantityKwh", title=None)
                fig = style_plotly(fig, section)
                st.plotly_chart(fig, width="stretch")
            else:
                st.dataframe(pie_df, use_container_width=True)
            st.caption(f"Year: **{DASHBOARD_YEAR}**")

    with right:
        st.markdown("**Monthly Trend (2021)**")
        groups_all = list_groups(area)
        selected_groups = st.multiselect(
            "Production groups",
            options=groups_all,
            default=groups_all[:3] if len(groups_all) > 3 else groups_all,
        )

        ym_list = list_months_for_year(area, DASHBOARD_YEAR)
        if not ym_list:
            st.info(f"No months found for {area} in {DASHBOARD_YEAR}.")
        else:
            label = st.selectbox("Month", ym_list, index=0)  # "YYYY-MM"
            y_sel, m_sel = map(int, label.split("-"))
            trend_df = monthly_series(area, selected_groups, y_sel, m_sel)
            if trend_df.empty:
                st.info("No records for these filters.")
            else:
                trend_df["date"] = pd.to_datetime(trend_df["date"])
                if USE_ALTAIR and alt is not None:
                    line = (
                        alt.Chart(trend_df)
                        .mark_line(point=True)
                        .encode(
                            x=alt.X("date:T", title="Date"),
                            y=alt.Y("quantityKwh:Q", title="Daily Total (kWh)"),
                            color=alt.Color("productionGroup:N", legend=alt.Legend(title="Group")),
                            tooltip=[
                                alt.Tooltip("productionGroup:N", title="Group"),
                                alt.Tooltip("date:T", title="Date"),
                                alt.Tooltip("quantityKwh:Q", title="kWh", format=",.0f"),
                            ],
                        )
                        .properties(height=360)
                    )
                    st.altair_chart(line, use_container_width=True)
                elif px is not None:
                    fig2 = px.line(trend_df, x="date", y="quantityKwh", color="productionGroup")
                    fig2.update_layout(xaxis_title="Date", yaxis_title="Daily Total (kWh)")
                    fig2 = style_plotly(fig2, section)
                    st.plotly_chart(fig2, width="stretch")
                else:
                    st.line_chart(
                        trend_df.pivot(index="date", columns="productionGroup", values="quantityKwh")
                    )
