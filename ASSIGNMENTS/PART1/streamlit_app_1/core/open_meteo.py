# core/open_meteo.py
import requests
import pandas as pd
import streamlit as st
from typing import Iterable

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
    """Download ERA5 hourly weather for a given year and location."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "hourly": ",".join(hourly_vars),
        "models": "era5",
        "timezone": timezone,
    }
    try: 
        r = requests.get(OPEN_METEO_BASE, params=params, timeout=60)
        r.raise_for_status()
    except requests.exceptions.Timeout as e:
        raise RuntimeError("Request to Open-Meteo API timed out") from e
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Request to Open-Meteo API failed: {e}") from e
    try:
        data = r.json()
    except ValueError as e:
        raise RuntimeError("Failed to parse JSON response from Open-Meteo API") from e
    hourly = data.get("hourly", {})
    if not hourly:
        raise RuntimeError("No hourly data found in Open-Meteo API response")
    df = pd.DataFrame(hourly)
    if df.empty:
        return df
    df = df.rename(columns={"time": "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df
