# pages/met_energy_corr.py
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

from core.ui import section_badge, apply_section_theme, style_plotly
from core.constants import AREAS_DF
from core.elhub_energy import load_area_energy_series, EnergyType
from core.geo_helpers import get_energy_groups


def _compute_sliding_correlation(
    df: pd.DataFrame,
    met_col: str,
    energy_col: str,
    window_hours: int,
    lag_hours: int,
) -> pd.DataFrame:
    """
    Sliding-window correlation between meteorological variable and energy.

    Positive lag_hours means: energy responds *after* meteorology
    (we shift energy backwards in time).
    """
    df = df[["time", met_col, energy_col]].dropna().sort_values("time")
    if df.empty:
        return pd.DataFrame(columns=["time", "corr"])

    df = df.set_index("time")

    # Shift energy series so that positive lag means 'energy after weather'
    if lag_hours != 0:
        df[f"{energy_col}_lagged"] = df[energy_col].shift(-lag_hours)
        y_col = f"{energy_col}_lagged"
    else:
        y_col = energy_col

    # Rolling correlation over window_hours samples (hourly data)
    rolling_corr = (
        df[met_col]
        .rolling(window=window_hours, min_periods=max(10, window_hours // 4))
        .corr(df[y_col])
    )

    out = rolling_corr.dropna().reset_index()
    out.columns = ["time", "corr"]
    return out


def render(section: str):
    apply_section_theme(section)
    section_badge("Met–Energy Correlation", section)
    st.title("Meteorology vs Energy Production / Consumption")

    # --- 1. Require weather data (wx2021) in session ------------------------
    wx = st.session_state.get("wx2021")
    if wx is None or wx.empty:
        st.info(
            "No weather data in memory. Go to **Electricity Production** (or the "
            "weather download page) and load ERA5 weather for 2021 first."
        )
        return

    # Ensure timestamp column is called 'timestamp' and is datetime
    if "timestamp" not in wx.columns:
        st.error("Weather dataframe is missing 'timestamp' column.")
        return

    wx = wx.copy()
    wx["timestamp"] = pd.to_datetime(wx["timestamp"])
    wx = wx.sort_values("timestamp")

    # --- 2. Area selection (consistent with rest of app) --------------------
    area_codes = AREAS_DF["area"].tolist()
    default_area = st.session_state.get("area", "NO5")
    if default_area not in area_codes:
        default_area = area_codes[0]

    c_area1, c_area2 = st.columns([1, 2])
    with c_area1:
        sel_area = st.selectbox("Price area", area_codes, index=area_codes.index(default_area))
    st.session_state.area = sel_area
    area = sel_area

    # Restrict to 2021 for now (since wx2021 == 2021)
    year = 2021
    start_ts = pd.Timestamp(year=year, month=1, day=1)
    end_ts = pd.Timestamp(year=year + 1, month=1, day=1)

    st.caption(f"Correlation period: **{year}-01-01 → {year+1}-01-01 (not inclusive)**")

    # --- 3. Selectors: met variable, energy type, energy group --------------
    st.subheader("Variables & parameters")

    # Meteorological variable options: numeric wx columns (except timestamp)
    met_candidates = [
        c for c in wx.columns
        if c != "timestamp" and pd.api.types.is_numeric_dtype(wx[c])
    ]
    if not met_candidates:
        st.error("Could not find any numeric meteorological variables in wx2021.")
        return

    col_vars1, col_vars2, col_vars3 = st.columns(3)

    with col_vars1:
        met_var = st.selectbox("Meteorological variable", met_candidates, index=0)

    with col_vars2:
        data_type: EnergyType = st.radio(
            "Energy type",
            options=["Production", "Consumption"],
            index=0,
            help="Switch between Elhub production and consumption datasets.",
        )

    with col_vars3:
        energy_groups = get_energy_groups(data_type)
        if not energy_groups:
            st.error(f"No {data_type.lower()} groups found in Elhub collections.")
            return
        energy_group = st.selectbox("Energy group", energy_groups)

    # Window length & lag
    col_params1, col_params2 = st.columns(2)
    with col_params1:
        window_hours = st.slider(
            "Window length (hours)",
            min_value=24,
            max_value=24 * 30,
            value=24 * 7,
            step=24,
            help="Length of the sliding window for correlation (in hours).",
        )
    with col_params2:
        lag_hours = st.slider(
            "Lag (hours, energy after weather)",
            min_value=-72,
            max_value=72,
            value=0,
            step=1,
            help=(
                "Positive lag: energy response occurs *after* the weather "
                "(energy time series shifted backward)."
            ),
        )

    if st.button("Compute sliding correlation", type="primary"):
        # --- 4. Load energy series from Elhub --------------------------------
        with st.spinner("Loading Elhub energy series from Mongo …"):
            energy_df = load_area_energy_series(
                energy_type=data_type,
                area=area,
                group=energy_group,
                start_ts=start_ts,
                end_ts=end_ts,
            )

        if energy_df is None or energy_df.empty:
            st.warning(
                f"No {data_type.lower()} data found for area {area}, "
                f"group '{energy_group}' in {year}."
            )
            return

        # --- 5. Align weather and energy on a common hourly time index -------
        wx_sub = wx[(wx["timestamp"] >= start_ts) & (wx["timestamp"] < end_ts)].copy()
        wx_sub = wx_sub[["timestamp", met_var]].rename(columns={"timestamp": "time"})

        # energy_df expected columns: ['time', 'kwh']
        energy_sub = energy_df.copy()
        energy_sub["time"] = pd.to_datetime(energy_sub["time"])

        merged = pd.merge(
            wx_sub,
            energy_sub,
            on="time",
            how="inner",
            validate="one_to_one",
        )
        if merged.empty:
            st.warning("No overlapping timestamps between weather and energy series.")
            return

        merged = merged.sort_values("time")
        merged.rename(columns={"kwh": "energy_kwh"}, inplace=True)

        # --- 6. Compute sliding correlation ----------------------------------
        corr_df = _compute_sliding_correlation(
            merged,
            met_col=met_var,
            energy_col="energy_kwh",
            window_hours=int(window_hours),
            lag_hours=int(lag_hours),
        )

        # --- 7. Show base series preview ------------------------------------
        st.markdown("### Data preview")
        st.write(
            f"Area **{area}**, {data_type.lower()} group **{energy_group}**, "
            f"met variable **{met_var}**."
        )
        st.dataframe(merged.head(100), use_container_width=True)

        # --- 8. Plot sliding correlation (Plotly) ----------------------------
        st.markdown("### Sliding-window correlation")

        if corr_df.empty:
            st.info(
                "Not enough data to compute correlation with the chosen window/lag. "
                "Try a shorter window or a different lag."
            )
        else:
            fig_corr = px.line(
                corr_df,
                x="time",
                y="corr",
                title=(
                    f"Sliding correlation: {met_var} vs {data_type.lower()} ({energy_group}) "
                    f"[window={window_hours}h, lag={lag_hours}h]"
                ),
                labels={"time": "Time", "corr": "Correlation"},
            )
            fig_corr.add_hline(y=0.0)
            fig_corr = style_plotly(fig_corr, section)
            st.plotly_chart(fig_corr, use_container_width=True)

        # --- 9. Scatter plot for the chosen period ---------------------------
        st.markdown("### Scatter plot (overall period)")

        fig_sc = px.scatter(
            merged,
            x=met_var,
            y="energy_kwh",
            opacity=0.3,
            trendline="ols",
            labels={met_var: met_var, "energy_kwh": "Energy (kWh)"},
            title=f"{met_var} vs {data_type.lower()} ({energy_group}) – overall",
        )
        fig_sc = style_plotly(fig_sc, section)
        st.plotly_chart(fig_sc, use_container_width=True)

        st.caption(
            "Correlation is computed using a sliding window over hourly data. "
            "Positive lag means the energy series is shifted backward in time, "
            "so peaks in meteorology precede peaks in energy."
        )
