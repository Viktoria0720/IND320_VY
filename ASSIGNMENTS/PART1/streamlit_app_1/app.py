"""
Created on Wed Sep  24 10:58:08 2023

@author: viyav
"""
# app.py
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
import requests

from typing import Iterable, Optional
from scipy.fft import dct, idct
from sklearn.neighbors import LocalOutlierFactor
from statsmodels.tsa.seasonal import STL
from scipy.signal import spectrogram

# Optional viz engines (graceful fallback)
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

# ---------- Streamlit page setup ----------
st.set_page_config(page_title="IND320 • Open-Meteo + Elhub", layout="wide")
st.markdown(
    """
    <style>
    .block-container {max-width: 1400px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------------
# GLOBAL STATE (shared across pages)
# -------------------------------------------------------
if "area" not in st.session_state:
    st.session_state.area = "NO5"   # default once
if "wx2021" not in st.session_state:
    st.session_state.wx2021 = None

# -------------------------------------------------------
# SHARED CONSTANTS
# -------------------------------------------------------
PRICE_AREAS = [
    {"area": "NO1", "city": "Oslo",         "lat": 59.9139,  "lon": 10.7522},
    {"area": "NO2", "city": "Kristiansand", "lat": 58.1467,  "lon": 7.9956},
    {"area": "NO3", "city": "Trondheim",    "lat": 63.4305,  "lon": 10.3951},
    {"area": "NO4", "city": "Tromsø",       "lat": 69.6492,  "lon": 18.9553},
    {"area": "NO5", "city": "Bergen",       "lat": 60.39299, "lon": 5.32415},
]
AREAS_DF = pd.DataFrame(PRICE_AREAS)

# -------------------------------------------------------
# OPEN-METEO ERA5 (replaces CSV)
# -------------------------------------------------------
OPEN_METEO_BASE = "https://archive-api.open-meteo.com/v1/era5"

@st.cache_data(show_spinner=True)
def get_era5_hourly(
    lat: float,
    lon: float,
    year: int = 2021,
    hourly_vars: Iterable[str] = (
        "temperature_2m",
        "relative_humidity_2m",
        "dew_point_2m",
        "apparent_temperature",
        "surface_pressure",
        "precipitation",
        "rain",
        "snowfall",
        "cloud_cover",
        "wind_speed_10m",
        "wind_direction_10m",
        "shortwave_radiation",
    ),
    timezone: str = "Europe/Oslo",
) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "hourly": ",".join(hourly_vars),
        "models": "era5",
        "timezone": timezone,
    }
    r = requests.get(OPEN_METEO_BASE, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    hourly = data.get("hourly", {})
    df = pd.DataFrame(hourly)
    if df.empty:
        return df
    df = df.rename(columns={"time": "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

# -------------------------------------------------------
# MONGO (Elhub) HELPERS
# -------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _get_mongo_collection():
    """
    Requires `.streamlit/secrets.toml`:
    [mongo]
    uri = "..."
    db = "energy"
    collection = "elhub_production_2021"
    """
    try:
        from pymongo import MongoClient
        import certifi
    except ModuleNotFoundError as e:
        st.error(
            f"Missing package: `{e.name}`. Install:\n\n"
            "  pip install pymongo certifi"
        )
        raise

    if "mongo" not in st.secrets:
        raise RuntimeError(
            "No [mongo] section in secrets. "
            "Add it to `.streamlit/secrets.toml` (local) or set Streamlit Cloud secrets."
        )

    uri = st.secrets["mongo"].get("uri")
    db_name = st.secrets["mongo"].get("db")
    coll_name = st.secrets["mongo"].get("collection")
    if not uri or not db_name or not coll_name:
        raise RuntimeError("Secrets missing one of: uri / db / collection.")

    client = MongoClient(uri, tls=True, tlsCAFile=certifi.where())
    db = client[db_name]
    return db[coll_name]

@st.cache_data(show_spinner=False)
def _list_price_areas() -> list[str]:
    coll = _get_mongo_collection()
    rows = coll.distinct("priceArea")
    rows = [r for r in rows if r is not None]
    return sorted(rows)




@st.cache_data(show_spinner=False)
def _list_groups(price_area: str) -> list[str]:
    coll = _get_mongo_collection()
    groups = coll.distinct("productionGroup", {"priceArea": price_area})
    groups = [g for g in groups if g is not None]
    return sorted(groups)

@st.cache_data(show_spinner=False)
def _list_year_months(price_area: str) -> list[str]:
    from pymongo import ASCENDING
    coll = _get_mongo_collection()
    pipeline = [
        {"$match": {"priceArea": price_area}},
        {"$project": {  # keep only what we need to minimize memory
            "startTime": 1, "_id": 0
        }},
        {"$addFields": {
            "time_dt": {
                "$cond": [
                    {"$eq": [{"$type": "$startTime"}, "date"]},
                    "$startTime",
                    {"$dateFromString": {"dateString": "$startTime", "onError": None, "onNull": None}}
                ]
            }
        }},
        {"$match": {"time_dt": {"$ne": None}}},
        {"$group": {"_id": {"y": {"$year": "$time_dt"}, "m": {"$month": "$time_dt"}}}},
        {"$sort": {"_id.y": ASCENDING, "_id.m": ASCENDING}},
    ]
    rows = _agg(coll, pipeline)
    return [f'{r["_id"]["y"]:04d}-{r["_id"]["m"]:02d}' for r in rows]

@st.cache_data(show_spinner=True)
def _monthly_series(price_area: str, groups: list[str], year: int, month: int) -> pd.DataFrame:
    from pymongo import ASCENDING
    coll = _get_mongo_collection()
    if not groups:
        groups = _list_groups(price_area)

    ym = f"{year:04d}-{month:02d}"
    pipeline = [
        {"$match": {"priceArea": price_area, "productionGroup": {"$in": groups}}},
        {"$project": {  # project early to shrink documents
            "_id": 0,
            "startTime": 1,
            "productionGroup": 1,
            "quantityKwh": 1,
        }},
        {"$addFields": {
            "time_dt": {
                "$cond": [
                    {"$eq": [{"$type": "$startTime"}, "date"]},
                    "$startTime",
                    {"$dateFromString": {"dateString": "$startTime", "onError": None, "onNull": None}}
                ]
            }
        }},
        {"$match": {"time_dt": {"$ne": None}}},
        {"$addFields": {
            "ym": {"$dateToString": {"format": "%Y-%m", "date": "$time_dt"}},
            "d":  {"$dateToString": {"format": "%Y-%m-%d", "date": "$time_dt"}},
        }},
        {"$match": {"ym": ym}},
        {"$group": {
            "_id": {"d": "$d", "g": "$productionGroup"},
            "quantityKwh": {"$sum": "$quantityKwh"},
        }},
        {"$project": {"_id": 0, "date": "$_id.d", "productionGroup": "$_id.g", "quantityKwh": 1}},
        {"$sort": {"date": ASCENDING, "productionGroup": ASCENDING}},
    ]
    return pd.DataFrame(_agg(coll, pipeline))


@st.cache_data(show_spinner=False)
def elhub_available_years(price_area: str) -> list[int]:
    coll = _get_mongo_collection()
    pipeline = [
        {"$match": {"priceArea": price_area}},
        {"$project": {"_id": 0, "startTime": 1}},
        {"$addFields": {
            "time_dt": {
                "$cond": [
                    {"$eq": [{"$type": "$startTime"}, "date"]},
                    "$startTime",
                    {"$dateFromString": {"dateString": "$startTime", "onError": None, "onNull": None}}
                ]
            }
        }},
        {"$match": {"time_dt": {"$ne": None}}},
        {"$group": {"_id": {"y": {"$year": "$time_dt"}}}},
        {"$sort": {"_id.y": 1}},
    ]
    rows = _agg(coll, pipeline)
    return [r["_id"]["y"] for r in rows]



@st.cache_data(show_spinner=True)
def load_elhub_for_area(price_area: str, year: int) -> pd.DataFrame:
    """
    Load Elhub production for (area, year). Robust to startTime string/BSON.
    No server-side $sort (to avoid 32MB sort limit) — we sort in pandas.
    Returns: ['time','area','group','production'] with Europe/Oslo tz-naive times.
    """
    coll = _get_mongo_collection()
    pipeline = [
        {"$match": {"priceArea": price_area}},
        {"$project": {  # keep docs small
            "_id": 0,
            "startTime": 1,
            "priceArea": 1,
            "productionGroup": 1,
            "quantityKwh": 1,
        }},
        {"$addFields": {  # coerce startTime to a proper date
            "time_dt": {
                "$cond": [
                    {"$eq": [{"$type": "$startTime"}, "date"]},
                    "$startTime",
                    {"$dateFromString": {"dateString": "$startTime", "onError": None, "onNull": None}}
                ]
            }
        }},
        {"$match": {"time_dt": {"$ne": None}}},
        {"$match": {"$expr": {"$eq": [{"$year": "$time_dt"}, year]}}},
        {"$project": {
            "time": "$time_dt",
            "area": "$priceArea",
            "group": "$productionGroup",
            "production": "$quantityKwh",
        }},
        # ⚠️ no $sort here — we'll sort client-side to avoid 32MB sort cap
    ]
    rows = _agg(coll, pipeline)  # allowDiskUse=True inside _agg
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # normalize types
    df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)\
                    .dt.tz_convert("Europe/Oslo").dt.tz_localize(None)
    df["production"] = pd.to_numeric(df["production"], errors="coerce")
    df["group"] = df["group"].astype(str).str.strip().str.replace("_", " ").str.title()

    # sort **client-side**
    df = df.dropna(subset=["time","production"]).sort_values("time")
    return df[["time","area","group","production"]]


@st.cache_data(show_spinner=True)
def load_elhub_for_area_2021(price_area: str) -> pd.DataFrame:
    return load_elhub_for_area(price_area, 2021)

    return df.dropna(subset=["time","production"]).sort_values("time")[["time","area","group","production"]]


def _agg(coll, pipeline):
    """Aggregate with disk spill enabled."""
    return list(coll.aggregate(pipeline, allowDiskUse=True))

# -------------------------------------------------------
# ANALYTICS HELPERS (STL, Spectrogram, SPC, LOF)
# -------------------------------------------------------
def stl_decompose_production(
    prod_df: pd.DataFrame,
    area: str,
    group: str,
    period: int = 24,
    seasonal: int = 13,
    trend: int = 101,
    robust: bool = True,
):
    if "time" not in prod_df.columns or "production" not in prod_df.columns:
        raise ValueError("prod_df must include 'time' and 'production' columns.")
    df = prod_df.copy()
    if "area" not in df.columns:  df["area"] = area
    if "group" not in df.columns: df["group"] = group
    df = df[(df["area"] == area) & (df["group"] == group)].sort_values("time")
    if df.empty:
        raise ValueError(f"No production for area={area}, group={group}")
    y = pd.Series(df["production"].to_numpy(float), index=pd.to_datetime(df["time"]))
    res = STL(y, period=period, seasonal=seasonal, trend=trend, robust=robust).fit()
    fig = res.plot(); fig.set_size_inches(11, 5); fig.suptitle(f"STL – {area}/{group}"); fig.tight_layout()
    return fig, res

def production_spectrogram(
    prod_df: pd.DataFrame, area: str, group: str, window_len: int = 24*7, overlap: float = 0.5,
):
    df = prod_df.copy()
    if "area" not in df.columns:  df["area"] = area
    if "group" not in df.columns: df["group"] = group
    df = df[(df["area"] == area) & (df["group"] == group)].sort_values("time")
    if df.empty:
        raise ValueError(f"No production for area={area}, group={group}")
    x = df["production"].to_numpy(float); fs = 1.0
    nperseg = int(window_len); noverlap = int(overlap * nperseg)
    f, t, Sxx = spectrogram(x, fs=fs, nperseg=nperseg, noverlap=noverlap, scaling="spectrum")
    fig, ax = plt.subplots(figsize=(11, 3.6))
    im = ax.pcolormesh(t, f, 10*np.log10(Sxx + 1e-12), shading="auto")
    ax.set_title(f"Spectrogram – {area}/{group}"); ax.set_xlabel("Window index"); ax.set_ylabel("Frequency [cycles/hour]")
    fig.colorbar(im, ax=ax, label="Power [dB]"); fig.tight_layout(); return fig

def spc_outliers_temperature(df: pd.DataFrame, dct_cutoff: float = 0.02, n_sigma: float = 3.5):
    ts = df[["timestamp", "temperature_2m"]].dropna().copy()
    x = ts["temperature_2m"].to_numpy(float)
    X = dct(x, type=2, norm="ortho"); k = max(1, int(len(X) * dct_cutoff))
    X_hp = X.copy(); X_hp[:k] = 0.0
    satv = idct(X_hp, type=2, norm="ortho"); satv_s = pd.Series(satv, index=ts.index, name="SATV")
    med = float(np.median(satv)); mad = float(np.median(np.abs(satv - med)))
    sigma = 1.4826*mad if mad > 0 else float(np.std(satv))
    upper = med + n_sigma*sigma; lower = med - n_sigma*sigma
    is_out = (satv_s > upper) | (satv_s < lower)
    out_df = ts.loc[is_out].assign(SATV=satv_s.loc[is_out])
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.plot(ts["timestamp"], ts["temperature_2m"], linewidth=1.0, label="Temperature")
    ax.scatter(out_df["timestamp"], out_df["temperature_2m"], s=10, color='crimson', label="Outlier")
    ax.set_title("Temperature & SPC Outliers (DCT high-pass)"); ax.set_ylabel("°C")
    ax.legend(); fig.tight_layout()
    return fig, out_df, pd.DataFrame([{
        "n": int(len(ts)), "n_outliers": int(is_out.sum()),
        "pct_outliers": float(is_out.mean()*100.0),
        "dct_cutoff": float(dct_cutoff), "n_sigma": float(n_sigma),
        "median_SATV": med, "sigma_robust": sigma, "upper_bound": upper, "lower_bound": lower,
    }])

def lof_precip_anomalies(df: pd.DataFrame, contamination: float = 0.01, n_neighbors: int = 35):
    sub = df[["timestamp", "precipitation"]].dropna().copy()
    y = sub["precipitation"].to_numpy(float).reshape(-1, 1)
    lof = LocalOutlierFactor(n_neighbors=n_neighbors, contamination=contamination)
    labels = lof.fit_predict(y)  # -1 = anomaly
    sub["lof_score"] = -lof.negative_outlier_factor_
    anoms = sub.loc[labels == -1]
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.plot(sub["timestamp"], sub["precipitation"], linewidth=1.0, label="Precipitation")
    ax.scatter(anoms["timestamp"], anoms["precipitation"], s=10, color='orange', label="LOF anomaly")
    ax.set_title("Precipitation & LOF anomalies"); ax.set_ylabel("mm")
    ax.legend(); fig.tight_layout()
    return fig, anoms, pd.DataFrame([{
        "n": int(len(sub)), "n_anomalies": int(len(anoms)),
        "pct_anomalies": float(100*len(anoms)/max(1,len(sub))),
        "contamination": float(contamination), "n_neighbors": int(n_neighbors),
    }])

# -------------------------------------------------------
# SIDEBAR NAVIGATION (assignment order)
# -------------------------------------------------------
PAGES = [
    "1 – Home",
    "4 – Area selector",          # ← this page also shows Mongo pie + monthly trend
    "new A – STL & Spectrogram",
    "2 – Data Table",
    "3 – Plots",
    "new B – Outliers & Anomalies",
    "5 – To be continued",
]
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", PAGES, index=0)

# -------------------------------------------------------
# PAGES
# -------------------------------------------------------

# PAGE 1: HOME
if page.startswith("1 –"):
    st.title("Welcome to the IND320 App 🌦️⚡")
    st.write("Select an area on **Page 4**. That selection drives the weather download (2021) and the Mongo views.")
    st.dataframe(AREAS_DF[["area","city","lon","lat"]], use_container_width=True)

# PAGE 4: AREA SELECTOR (drives weather + shows Mongo pie & trend)
elif page.startswith("4 –"):
    st.title("Select Electricity Price Area")
    area_codes = AREAS_DF["area"].tolist()
    default_idx = area_codes.index(st.session_state.area) if st.session_state.area in area_codes else 0
    area = st.radio("Price area", area_codes, index=default_idx, horizontal=True)
    st.session_state.area = area

    # Weather download for the selected area (2021)
    row = AREAS_DF[AREAS_DF["area"] == area].iloc[0]
    with st.spinner(f"Downloading ERA5 hourly weather for {row.city} (2021) from Open-Meteo..."):
        wx = get_era5_hourly(row.lat, row.lon, 2021)
    st.session_state.wx2021 = wx
    st.success(f"Downloaded {len(wx)} rows for {row.city} / {area} (2021).")

    # ---- Mongo pie + monthly trend (same page) ----
    st.divider()
    st.subheader("Elhub – Production overview (MongoDB)")
    # Connection probe
    try:
        _ = _get_mongo_collection().estimated_document_count()
    except Exception as e:
        st.error("Could not connect to MongoDB.")
        with st.expander("Technical details"): st.exception(e)
        st.stop()

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**Distribution by Production Group**")
        pie_df = _totals_for_area(area)
        if pie_df.empty:
            st.info("No data for the selected area.")
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
                    ).properties(height=360)
                )
                st.altair_chart(chart, use_container_width=True)
            elif px is not None:
                fig = px.pie(pie_df, names="productionGroup", values="quantityKwh", title=None)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.dataframe(pie_df, use_container_width=True)

    with right:
        st.markdown("**Monthly Trend**")
        groups_all = _list_groups(area)
        if hasattr(st, "pills"):
            selected_groups = st.pills(
                "Production groups",
                options=groups_all,
                selection_mode="multi",
                default=groups_all[:3] if len(groups_all) > 3 else groups_all,
            )
        else:
            selected_groups = st.multiselect(
                "Production groups",
                options=groups_all,
                default=groups_all[:3] if len(groups_all) > 3 else groups_all,
            )

        ym_list = _list_year_months(area)
        if not ym_list:
            st.info("No months found for the selected area.")
        else:
            label = st.selectbox("Month", ym_list, index=0)  # "YYYY-MM"
            y_sel, m_sel = map(int, label.split("-"))
            trend_df = _monthly_series(area, selected_groups, y_sel, m_sel)
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
                        ).properties(height=360)
                    )
                    st.altair_chart(line, use_container_width=True)
                elif px is not None:
                    fig2 = px.line(trend_df, x="date", y="quantityKwh", color="productionGroup")
                    fig2.update_layout(xaxis_title="Date", yaxis_title="Daily Total (kWh)")
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.line_chart(
                        trend_df.pivot(index="date", columns="productionGroup", values="quantityKwh")
                    )

# -------------------------------
# PAGE new A: STL & Spectrogram (choose available year)
# -------------------------------
elif page.startswith("new A –"):
    st.title("new A – STL & Spectrogram (Elhub production)")

    # Area stays in session and defaults to your previous choice
    area_codes = AREAS_DF["area"].tolist()
    default_idx = area_codes.index(st.session_state.area) if st.session_state.area in area_codes else 0
    sel_area = st.selectbox("Area", area_codes, index=default_idx)
    if sel_area != st.session_state.area:
        st.session_state.area = sel_area
    area = st.session_state.area

    # Figure out which years exist for this area
    years = elhub_available_years(area)
    if not years:
        st.error(f"No production data found for {area}.")
        st.stop()

    # Prefer 2021 if present; otherwise use the latest available
    default_year = 2021 if 2021 in years else years[-1]
    year = st.selectbox("Year", years, index=years.index(default_year))

    # Load data for (area, year)
    with st.spinner(f"Loading Elhub production for {area} in {year} …"):
        prod_df = load_elhub_for_area(area, year)

    if prod_df.empty:
        st.warning(f"No production data for {area} in {year}. Try another year.")
        st.stop()

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
        st.pyplot(fig, use_container_width=True)

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
        st.pyplot(fig, use_container_width=True)

    with st.expander("Data info"):
        st.write(f"Area: **{area}**  •  Year: **{year}**  •  Rows: **{len(prod_df):,}**")
        st.dataframe(prod_df.head(), use_container_width=True)


# PAGE 2: DATA TABLE (Open-Meteo 2021)
elif page.startswith("2 –"):
    area = st.session_state.area
    st.title(f"Weather Data Table (Open-Meteo 2021) — {area}")
    wx = st.session_state.get("wx2021")
    if wx is None or wx.empty:
        st.info("Go to '4 – Area selector' to download weather for 2021 first.")
        st.stop()

    st.write("First month of the dataset, row-wise sparklines per variable:")
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

    st.divider()
    st.write("Alternate rendering (mini line charts per row):")
    col1, col2 = st.columns([1, 3])
    col1.write("**Variable**")
    col2.write("**First Month Trend**")
    for col_name in data_only.columns:
        c1, c2 = st.columns([1, 3])
        c1.write(col_name)
        c2.line_chart(df_first_month.set_index("timestamp")[[col_name]], height=160)

# PAGE 3: PLOTS (weather)
elif page.startswith("3 –"):
    area = st.session_state.area
    st.title(f"Weather Plots (Open-Meteo 2021) — {area}")
    wx = st.session_state.get("wx2021")
    if wx is None or wx.empty:
        st.info("Go to '4 – Area selector' to download weather for 2021 first.")
        st.stop()

    options = ["All columns"] + [c for c in wx.columns if c != "timestamp"]
    column_choice = st.selectbox("Select column(s) to plot", options)

    months = sorted(wx["timestamp"].dt.to_period("M").unique())
    month_selected = st.select_slider("Select a month", options=months, value=months[0])
    month_df = wx[wx["timestamp"].dt.to_period("M") == month_selected]

    fig, ax = plt.subplots(figsize=(10, 4))
    if column_choice == "All columns":
        for col in wx.columns:
            if col != "timestamp":
                ax.plot(month_df["timestamp"], month_df[col], label=col)
    else:
        ax.plot(month_df["timestamp"], month_df[column_choice], label=column_choice)

    ax.set_title(f"Weather for {month_selected}"); ax.set_xlabel("Time"); ax.set_ylabel("Value")
    ax.legend(loc="upper right", ncols=2, fontsize=8)
    st.pyplot(fig, use_container_width=True)

# PAGE new B: Outliers & Anomalies (tabs on weather)
elif page.startswith("new B –"):
    area = st.session_state.area
    st.title(f"new B – Outliers & Anomalies (Weather 2021) — {area}")
    wx = st.session_state.get("wx2021")
    if wx is None or wx.empty:
        st.info("Go to '4 – Area selector' to download weather for 2021 first.")
        st.stop()

    tab1, tab2 = st.tabs(["Outlier / SPC (Temperature)", "Anomaly / LOF (Precipitation)"])
    with tab1:
        st.subheader("SPC via DCT (SATV)")
        c1, c2 = st.columns(2)
        dct_cutoff = c1.slider("DCT cutoff (fraction)", 0.0, 0.2, 0.02, 0.005)
        n_sigma = c2.slider("Sigma multiplier", 1.0, 6.0, 3.5, 0.1)
        fig, out_df, summary_df = spc_outliers_temperature(wx, dct_cutoff=float(dct_cutoff), n_sigma=float(n_sigma))
        st.pyplot(fig, use_container_width=True)
        st.write("Summary:", summary_df)
        st.write("Outlier samples:", out_df.head(50))

    with tab2:
        st.subheader("LOF anomalies (precipitation)")
        c1, c2 = st.columns(2)
        contamination = c1.slider("Expected outlier proportion", 0.001, 0.1, 0.01, 0.001)
        n_neighbors = c2.slider("LOF neighbors", 10, 80, 35, 1)
        fig, anoms_df, summary_df = lof_precip_anomalies(wx, contamination=float(contamination), n_neighbors=int(n_neighbors))
        st.pyplot(fig, use_container_width=True)
        st.write("Summary:", summary_df)
        st.write("Anomaly samples:", anoms_df.head(50))

# PAGE 5: DUMMY / CLOSING
elif page.startswith("5 –"):
    st.title("Keep Calm and Don’t Give Up on Coding 💻")
    st.markdown(
        "<div style='background-color:#245; color:white; font-size:40px; "
        "text-align:center; padding:50px;'>You're almost there! 🚀</div>",
        unsafe_allow_html=True,
    )
