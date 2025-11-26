# pages/weather_overview.py
import numpy as np
import pandas as pd
import streamlit as st

try:
    import plotly.express as px
except Exception:
    px = None

from core.ui import section_badge, apply_section_theme, style_plotly


def render(section: str):
    area = st.session_state.get("area", "NO5")
    apply_section_theme(section)
    section_badge("Open-Meteo – Weather", section)
    st.title(f"Weather Overview (Open-Meteo 2021) — {area}")

    wx = st.session_state.get("wx2021")
    if wx is None or wx.empty:
        st.info("Go to **Elhub – Production → Production Dashboard** to download weather for 2021 first.")
        return

    tab_table, tab_plots = st.tabs(["Table & LineChartColumn", "Interactive Plots"])

    with tab_table:
        st.subheader("Hourly weather – first month snapshot")
        first_month = wx["timestamp"].dt.to_period("M").min()
        df_first_month = wx[wx["timestamp"].dt.to_period("M") == first_month].copy()
        data_only = df_first_month.drop(columns=["timestamp"])
        reshaped = pd.DataFrame({
            "Variable": data_only.columns,
            "Trend": [data_only[c].tolist() for c in data_only.columns],
        })
        st.dataframe(
            reshaped,
            column_config={
                "Variable": st.column_config.TextColumn("Variable"),
                "Trend": st.column_config.LineChartColumn(
                    "First Month Series",
                    y_min=float(np.nanmin(data_only.values)),
                    y_max=float(np.nanmax(data_only.values)),
                    width="large",
                ),
            },
            hide_index=True,
            use_container_width=True,
        )

    with tab_plots:
        st.subheader("Interactive time series (Plotly)")
        if px is None:
            st.warning("Plotly is not installed. Run `pip install plotly` to enable interactive plots.")
        else:
            options = ["All variables"] + [c for c in wx.columns if c != "timestamp"]
            column_choice = st.selectbox("Select variable(s)", options)

            months = sorted(wx["timestamp"].dt.to_period("M").unique())
            month_selected = st.select_slider("Select a month", options=months, value=months[0])
            month_df = wx[wx["timestamp"].dt.to_period("M") == month_selected]

            if column_choice == "All variables":
                long_df = month_df.melt(
                    id_vars="timestamp",
                    var_name="variable",
                    value_name="value",
                )
                fig = px.line(
                    long_df,
                    x="timestamp",
                    y="value",
                    color="variable",
                    labels={"value": "Value", "timestamp": "Time"},
                )
            else:
                fig = px.line(
                    month_df,
                    x="timestamp",
                    y=column_choice,
                    labels={column_choice: column_choice, "timestamp": "Time"},
                )

            fig.update_layout(
                title=f"Weather for {month_selected}",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                hovermode="x unified",
            )
            fig = style_plotly(fig, section)
            st.plotly_chart(fig, use_container_width=True)
