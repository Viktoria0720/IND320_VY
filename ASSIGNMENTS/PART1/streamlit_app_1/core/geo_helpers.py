# core/geo_helpers.py
import pandas as pd
import streamlit as st

from core.constants import AREAS_DF
from core.mongo_elhub import load_elhub_for_area, list_groups

AREA_CODES = AREAS_DF["area"].tolist()

@st.cache_data(show_spinner=True)
def get_production_groups() -> list[str]:
    """
    Return a sorted list of production groups available somewhere
    (we just sample from NO1 to avoid scanning everything).
    """
    sample_area = AREA_CODES[0]
    groups = list_groups(sample_area)
    return sorted(groups)

@st.cache_data(show_spinner=True)
def mean_production_by_area(group: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """
    Compute mean hourly production for each area in [start, end)
    for the given production group. Assumes interval stays inside one calendar year.
    """
    results = []
    year = start.year

    for area in AREA_CODES:
        df = load_elhub_for_area(area, year)
        if df.empty:
            mean_val = float("nan")
        else:
            mask = (
                (df["group"] == group) &
                (df["time"] >= start) &
                (df["time"] < end)
            )
            mean_val = df.loc[mask, "production"].mean()

        results.append({"area": area, "mean_value": float(mean_val) if pd.notna(mean_val) else 0.0})

    return pd.DataFrame(results)

@st.cache_data(show_spinner=True)
def _area_to_feature_code(area_code: str) -> str:
    """
    Convert internal code 'NO1' to the GeoJSON code 'NO 1', etc.
    """
    area_code = area_code.strip().upper()
    if area_code.startswith("NO") and len(area_code) == 3:
        return f"NO {area_code[-1]}"
    return area_code
