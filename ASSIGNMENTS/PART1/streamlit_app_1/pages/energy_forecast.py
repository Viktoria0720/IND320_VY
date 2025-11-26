# pages/energy_forecast.py
import numpy as np
import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
except Exception:
    go = None

try:
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    HAS_SARIMAX = True
except Exception:
    SARIMAX = None
    HAS_SARIMAX = False

from core.ui import section_badge, apply_section_theme, style_plotly
from core.constants import AREAS_DF
from core.elhub_energy import (
    load_area_energy_series,
    EnergyType,
    _get_elhub_collections,
    _normalize_group_name,
)


@st.cache_data(show_spinner=True)
def get_energy_groups(energy_type: EnergyType) -> list[str]:
    """
    Fetch distinct production/consumption groups from Mongo
    and normalise their names to match load_area_energy_series().
    """
    coll_prod, coll_cons = _get_elhub_collections()
    coll = coll_prod if energy_type == "Production" else coll_cons
    field = "productionGroup" if energy_type == "Production" else "consumptionGroup"

    raw_groups = coll.distinct(field)
    groups = {_normalize_group_name(g) for g in raw_groups if g is not None}
    return sorted(groups)


def render(section: str):
    apply_section_theme(section)
    section_badge("Elhub – Forecasting", section)
    st.title("SARIMAX Forecast – Energy Production & Consumption")

    if not HAS_SARIMAX:
        st.error(
            "statsmodels is not installed. Add `statsmodels` to your "
            "`requirements.txt` to use the SARIMAX forecasting page."
        )
        return

    # --- 1. Basic selections: area, energy type, group -----------------------
    area_codes = AREAS_DF["area"].tolist()
    default_area = st.session_state.get("area", "NO5")
    if default_area not in area_codes:
        default_area = area_codes[0]

    c0, c1, c2 = st.columns(3)
    with c0:
        area = st.selectbox("Price area", area_codes, index=area_codes.index(default_area))
    st.session_state.area = area

    with c1:
        energy_type: EnergyType = st.radio(
            "Energy type",
            options=["Production", "Consumption"],
            index=0,
            help="Choose whether to forecast production or consumption.",
        )

    with c2:
        groups = get_energy_groups(energy_type)
        if not groups:
            st.error(f"No {energy_type.lower()} groups found in Mongo.")
            return
        group = st.selectbox("Energy group", groups)

    # --- 2. Training period & forecast horizon ------------------------------
    st.subheader("Training period & forecast horizon")

    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1:
        train_start = st.date_input("Training start", pd.to_datetime("2021-01-01"))
    with col_t2:
        train_end = st.date_input("Training end", pd.to_datetime("2021-12-31"))
    with col_t3:
        horizon_days = st.number_input(
            "Forecast horizon (days)",
            min_value=1,
            max_value=60,
            value=7,
            step=1,
        )

    if train_end < train_start:
        st.error("Training end date must be on or after start date.")
        return

    start_ts = pd.to_datetime(train_start)
    end_ts = pd.to_datetime(train_end) + pd.Timedelta(days=1)  # make end exclusive
    steps = int(horizon_days) * 24  # hourly horizon

    # --- 3. Exogenous variables from weather (optional) ---------------------
    wx = st.session_state.get("wx2021")
    exog_vars: list[str] = []
    if wx is not None and not wx.empty:
        wx = wx.copy()
        wx["timestamp"] = pd.to_datetime(wx["timestamp"])
        # numeric columns as candidates
        met_candidates = [
            c for c in wx.columns
            if c != "timestamp" and pd.api.types.is_numeric_dtype(wx[c])
        ]
        with st.expander("Optional: meteorological exogenous variables", expanded=False):
            exog_vars = st.multiselect(
                "Select exogenous weather variables (used in training & forecast)",
                options=met_candidates,
            )
    else:
        st.info(
            "No weather data in memory (wx2021). You can still run SARIMAX without exogenous variables."
        )

    # --- 4. SARIMAX parameter controls --------------------------------------
    st.subheader("SARIMAX parameters")

    c_p, c_d, c_q = st.columns(3)
    with c_p:
        p = st.number_input("AR order (p)", min_value=0, max_value=5, value=1, step=1)
    with c_d:
        d = st.number_input("Differencing (d)", min_value=0, max_value=2, value=0, step=1)
    with c_q:
        q = st.number_input("MA order (q)", min_value=0, max_value=5, value=1, step=1)

    c_P, c_D, c_Q, c_s = st.columns(4)
    with c_P:
        P = st.number_input("Seasonal AR (P)", min_value=0, max_value=3, value=0, step=1)
    with c_D:
        D = st.number_input("Seasonal diff (D)", min_value=0, max_value=1, value=0, step=1)
    with c_Q:
        Q = st.number_input("Seasonal MA (Q)", min_value=0, max_value=3, value=0, step=1)
    with c_s:
        seasonal_period = st.number_input(
            "Seasonal period (s, hours)",
            min_value=0,
            max_value=24 * 14,
            value=24,
            step=24,
            help="0 disables seasonality; 24 = daily, 24*7 = weekly for hourly data.",
        )

    if st.button("Run SARIMAX forecast", type="primary"):
        # --- 5. Load energy series ------------------------------------------
        with st.spinner("Loading energy series from Mongo…"):
            energy_df = load_area_energy_series(
                energy_type=energy_type,
                area=area,
                group=group,
                start_ts=start_ts,
                end_ts=end_ts,
            )

        if energy_df is None or energy_df.empty:
            st.warning(
                f"No {energy_type.lower()} data found for area {area}, "
                f"group '{group}' in the chosen period."
            )
            return

        # Use hourly time index and kWh as target
        energy_df = energy_df.copy()
        energy_df["time"] = pd.to_datetime(energy_df["time"])
        energy_df = energy_df.sort_values("time")

        y = energy_df.set_index("time")["kwh"]
        if y.size < 48:
            st.warning("Not enough data in the training window (need at least 48 points).")
            return

        # --- 6. Build exogenous matrices -----------------------------------
        exog_train = None
        exog_forecast = None

        if exog_vars:
            if wx is None or wx.empty:
                st.warning("No weather data available; ignoring selected exogenous variables.")
            else:
                wx_sub = wx[["timestamp"] + exog_vars].copy()
                wx_sub.rename(columns={"timestamp": "time"}, inplace=True)
                wx_sub["time"] = pd.to_datetime(wx_sub["time"])

                # Join to ensure exog is aligned to y
                ex = pd.merge(
                    energy_df[["time"]],
                    wx_sub,
                    on="time",
                    how="left",
                )
                ex = ex.set_index("time")[exog_vars].fillna(method="ffill").fillna(method="bfill")

                exog_train = ex.loc[y.index]

        # Future index: assume hourly data
        last_time = y.index[-1]
        freq = pd.Timedelta(hours=1)
        future_index = pd.date_range(last_time + freq, periods=steps, freq=freq)

        if exog_train is not None:
            last_exog = exog_train.iloc[-1]
            exog_forecast = pd.DataFrame(
                np.tile(last_exog.values, (steps, 1)),
                columns=exog_train.columns,
                index=future_index,
            )

        # --- 7. Fit SARIMAX and forecast ------------------------------------
        order = (int(p), int(d), int(q))
        if seasonal_period > 0:
            seasonal_order = (int(P), int(D), int(Q), int(seasonal_period))
        else:
            seasonal_order = (0, 0, 0, 0)

        try:
            model = SARIMAX(
                endog=y,
                exog=exog_train,
                order=order,
                seasonal_order=seasonal_order,
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            results = model.fit(disp=False)
        except Exception as e:
            st.error("SARIMAX failed to fit with the chosen parameters.")
            with st.expander("Show error details"):
                st.exception(e)
            return

        try:
            forecast_res = results.get_forecast(steps=steps, exog=exog_forecast)
        except Exception as e:
            st.error("Forecasting failed (exogenous mismatch or model issue).")
            with st.expander("Show error details"):
                st.exception(e)
            return

        fc_mean = forecast_res.predicted_mean
        conf_int = forecast_res.conf_int(alpha=0.05)

        # Align CI column names
        if conf_int.shape[1] == 2:
            conf_int.columns = ["lower", "upper"]
        else:
            # statsmodels sometimes names them like 'lower y', 'upper y'
            lower_col = [c for c in conf_int.columns if "lower" in c.lower()][0]
            upper_col = [c for c in conf_int.columns if "upper" in c.lower()][0]
            conf_int = conf_int[[lower_col, upper_col]].rename(
                columns={lower_col: "lower", upper_col: "upper"}
            )

        # --- 8. Assemble plot DataFrame -------------------------------------
        hist_df = y.to_frame(name="y")
        fc_df = pd.DataFrame(
            {
                "time": future_index,
                "forecast": fc_mean.values,
                "lower": conf_int["lower"].values,
                "upper": conf_int["upper"].values,
            }
        ).set_index("time")

        # --- 9. Plot with Plotly -------------------------------------------
        if go is None:
            st.error("plotly is not installed; add `plotly` to requirements.txt.")
        else:
            fig = go.Figure()

            fig.add_trace(
                go.Scatter(
                    x=hist_df.index,
                    y=hist_df["y"],
                    mode="lines",
                    name="Observed",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=fc_df.index,
                    y=fc_df["forecast"],
                    mode="lines",
                    name="Forecast",
                )
            )
            # Confidence band
            fig.add_trace(
                go.Scatter(
                    x=fc_df.index.tolist() + fc_df.index[::-1].tolist(),
                    y=fc_df["upper"].tolist() + fc_df["lower"][::-1].tolist(),
                    fill="toself",
                    name="95% CI",
                    opacity=0.2,
                    line=dict(width=0),
                    showlegend=True,
                )
            )

            fig.update_layout(
                title=(
                    f"SARIMAX forecast for {energy_type.lower()} – {group} in {area} "
                    f"(horizon {horizon_days} days)"
                ),
                xaxis_title="Time",
                yaxis_title="Energy (kWh)",
            )
            fig = style_plotly(fig, section)
            st.plotly_chart(fig, width="stretch")

        # --- 10. Model summary snippet --------------------------------------
        with st.expander("Model summary (truncated)"):
            st.text(str(results.summary())[:2000])
