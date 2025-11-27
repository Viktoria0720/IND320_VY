# pages/snow_drift_page.py
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

try:
    import plotly.express as px
except Exception:
    px = None

from core.ui import section_badge, apply_section_theme, style_plotly
from core.open_meteo import get_era5_hourly


# --- Tabler helper functions (adapted from Snow_drift.py) --------------------


def compute_Qupot(hourly_wind_speeds, dt: int = 3600) -> float:
    """Potential wind-driven snow transport [kg/m] using u^3.8."""
    total = sum((u ** 3.8) * dt for u in hourly_wind_speeds) / 233847
    return float(total)


def sector_index(direction: float) -> int:
    """Map a wind direction in degrees to one of 16 sectors (0–15)."""
    return int(((direction + 11.25) % 360) // 22.5)


def compute_sector_transport(hourly_wind_speeds, hourly_wind_dirs, dt: int = 3600):
    """Directional breakdown of transport for a 16-sector wind rose."""
    sectors = [0.0] * 16
    for u, d in zip(hourly_wind_speeds, hourly_wind_dirs):
        idx = sector_index(d)
        sectors[idx] += ((u ** 3.8) * dt) / 233847
    return sectors


def compute_snow_transport(
    T: float,
    F: float,
    theta: float,
    Swe: float,
    hourly_wind_speeds,
    dt: int = 3600,
) -> dict:
    """Tabler (2003) snow transport bookkeeping for one season."""
    Qupot = compute_Qupot(hourly_wind_speeds, dt)
    Qspot = 0.5 * T * Swe   # snowfall-limited transport [kg/m]
    Srwe = theta * Swe      # relocated water equivalent [mm]

    if Qupot > Qspot:
        Qinf = 0.5 * T * Srwe
        control = "Snowfall controlled"
    else:
        Qinf = Qupot
        control = "Wind controlled"

    Qt = Qinf * (1 - 0.14 ** (F / T))

    return {
        "Qupot (kg/m)": Qupot,
        "Qspot (kg/m)": Qspot,
        "Srwe (mm)": Srwe,
        "Qinf (kg/m)": Qinf,
        "Qt (kg/m)": Qt,
        "Control": control,
    }


def plot_rose(avg_sector_values, overall_avg: float):
    """Matplotlib wind-rose for average directional transport (tonnes/m)."""
    fig, ax = plt.subplots(subplot_kw={"projection": "polar"}, figsize=(6, 6))

    num_sectors = 16
    angles = np.deg2rad(np.arange(0, 360, 360 / num_sectors))

    # convert sector transport from kg/m to tonnes/m
    avg_sector_values_tonnes = np.asarray(avg_sector_values, dtype=float) / 1000.0

    ax.bar(
        angles,
        avg_sector_values_tonnes,
        width=np.deg2rad(360 / num_sectors),
        align="center",
        edgecolor="black",
    )

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)

    directions = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
    ]
    ax.set_xticks(angles)
    ax.set_xticklabels(directions)

    overall_tonnes = overall_avg / 1000.0
    ax.set_title(
        f"Average Directional Snow Transport\nOverall Qt: {overall_tonnes:,.1f} tonnes/m",
        va="bottom",
    )
    plt.tight_layout()
    return fig


# --- Weather helpers: ERA5 for July–June "seasons" ---------------------------


@st.cache_data(show_spinner=True)
def load_season_weather(lat: float, lon: float, season_start_year: int) -> pd.DataFrame:
    """
    Download ERA5 for a July–June “snow season” around *season_start_year*.

    We re-use get_era5_hourly (calendar years) and then slice out
    [1 July season_start_year, 30 June season_start_year+1].
    """
    # Two calendar years of data
    df1 = get_era5_hourly(lat, lon, season_start_year)
    df2 = get_era5_hourly(lat, lon, season_start_year + 1)

    wx = pd.concat([df1, df2], ignore_index=True)
    if wx.empty:
        return wx

    wx = wx.copy()
    start = pd.Timestamp(season_start_year, 7, 1)
    end = pd.Timestamp(season_start_year + 1, 6, 30, 23, 59, 59)
    wx = wx[(wx["timestamp"] >= start) & (wx["timestamp"] <= end)]

    # Season label = start year (e.g. 2021 for 2021–2022)
    wx["season"] = season_start_year
    return wx.reset_index(drop=True)


def compute_snow_drift_for_range(
    lat: float,
    lon: float,
    start_year: int,
    end_year: int,
    T: float = 3000.0,
    F: float = 30000.0,
    theta: float = 0.5,
    progress=None,
    status=None,
):
    """
    Loop over seasons start_year … end_year and return
    (results_df, avg_sectors, overall_avg_Qt).
    """
    season_rows = []
    sector_arrays = []
    years = list(range(start_year, end_year + 1))

    for i, year in enumerate(years):
        if status is not None:
            status.write(f"Computing snow drift for season {year}-{year+1} …")

        wx = load_season_weather(lat, lon, year)
        if wx.empty:
            continue

        if progress is not None:
            progress.progress((i + 1) / len(years))

        # Hourly Swe: precipitation when T < +1°C
        wx = wx.copy()
        wx["Swe_hourly"] = np.where(wx["temperature_2m"] < 1.0, wx["precipitation"], 0.0)
        Swe_total = float(wx["Swe_hourly"].sum())

        wind_speeds = wx["wind_speed_10m"].to_numpy(float)
        wind_dirs = wx["wind_direction_10m"].to_numpy(float)

        # Tabler snow-drift calculation for this season
        res = compute_snow_transport(T, F, theta, Swe_total, wind_speeds)
        res["season"] = f"{year}-{year+1}"
        season_rows.append(res)

        # Directional transport for wind-rose
        sectors = compute_sector_transport(wind_speeds, wind_dirs)
        sector_arrays.append(sectors)

    if not season_rows:
        return pd.DataFrame(), None, None

    df = pd.DataFrame(season_rows)
    overall_avg_Qt = float(df["Qt (kg/m)"].mean())
    avg_sectors = np.mean(np.array(sector_arrays), axis=0) if sector_arrays else None
    return df, avg_sectors, overall_avg_Qt


# --- Streamlit page ----------------------------------------------------------


def render(section: str):
    apply_section_theme(section)
    section_badge("Open-Meteo – Weather", section)
    st.title("Snow Drift & Wind Rose (Tabler 2003)")

    # 1) Require a clicked coordinate from the map page
    last_clicked = st.session_state.get("last_clicked")
    if not last_clicked:
        st.info(
            "No coordinate selected yet. Go to **Maps → Price Area Map**, click a point, "
            "and then come back here."
        )
        return

    lat = float(last_clicked["lat"])
    lon = float(last_clicked["lng"])
    st.markdown(f"**Using coordinate:** `{lat:.4f}°N, {lon:.4f}°E` (from map page)")

    # 2) Controls: year range + (optional) Tabler parameters
    st.subheader("Snow drift per season (Jul–Jun)")
    col1, col2 = st.columns(2)

    with col1:
        start_year, end_year = st.select_slider(
            "Season start years (Jul–Jun)",
            options=list(range(2010, 2025)),
            value=(2018, 2021),
        )

    with col2:
        with st.expander("Advanced Tabler parameters", expanded=False):
            T = st.number_input("Transport distance T [m]", 1000.0, 10000.0, 3000.0, step=500.0)
            F = st.number_input("Fetch distance F [m]", 5000.0, 80000.0, 30000.0, step=5000.0)
            theta = st.slider("Relocation coefficient θ", 0.1, 1.0, 0.5, 0.05)

    if end_year < start_year:
        st.error("End year must be ≥ start year.")
        return

    # 3) Button → do the actual work
    if st.button("Compute snow drift", type="primary"):
        progress = st.progress(0.0)
        status = st.empty()
        try:
            with st.spinner("Downloading ERA5 data and computing snow drift …"):
                results_df, avg_sectors, overall_avg_Qt = compute_snow_drift_for_range(
                    lat, lon, start_year, end_year, T=T, F=F, theta=theta, progress=progress, status=status
                )
        except Exception as e:
            progress.empty()
            status.empty()
            st.error("Could not download ERA5 data or compute snow drift.")
            with st.expander("Show technical details"):
                st.exception(e)
            return

        if results_df.empty:
            st.warning("No weather data returned for this year range – try a different range.")
            return

        # 4) Tabular results
        st.markdown("### Seasonal results")
        results_disp = results_df.copy()
        results_disp["Qt (tonnes/m)"] = results_disp["Qt (kg/m)"] / 1000.0
        st.dataframe(
            results_disp[["season", "Qt (tonnes/m)", "Control"]].style.format(
                {"Qt (tonnes/m)": "{:.1f}"}
            ),
            use_container_width=True,
        )

        # 5) Plot Qt vs season (Plotly bar chart)
        if px is not None:
            fig = px.bar(
                results_disp,
                x="season",
                y="Qt (tonnes/m)",
                labels={"season": "Season (Jul–Jun)", "Qt (tonnes/m)": "Qt [tonnes/m]"},
                title="Mean annual snow transport per season",
            )
            fig = style_plotly(fig, section)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Plotly not installed – showing raw table only.")

        # 6) Wind-rose using the average sector transport
        st.markdown("### Wind rose (average directional distribution)")
        if avg_sectors is None:
            st.info("Could not compute directional breakdown.")
        else:
            fig_rose = plot_rose(avg_sectors, overall_avg_Qt)
            st.pyplot(fig_rose, use_container_width=True)

        # 7) Tiny summary
        st.caption(
            "Snow drift is computed using hourly ERA5 data, defining a season as 1 July–30 June. "
            "Swe is precipitation when temperature < +1°C, and Qt follows Tabler (2003)."
        )
