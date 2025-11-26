# core/geo_helpers.py
import pandas as pd
import streamlit as st

from core.constants import AREAS_DF
from core.mongo_elhub import list_groups
from core.elhub_energy import load_area_energy_series, _get_elhub_collections


AREA_CODES = AREAS_DF["area"].tolist()


@st.cache_data(show_spinner=True)
def get_production_groups() -> list[str]:
    """
    Return a sorted list of production groups available somewhere
    (we just sample from the first area to avoid scanning everything).
    """
    sample_area = AREA_CODES[0]
    groups = list_groups(sample_area)
    return sorted(groups)


@st.cache_data(show_spinner=True)
def mean_energy_by_area(
    data_type: str,  # "Production" or "Consumption"
    group: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    """
    Compute mean hourly energy for each area in [start, end)
    for the given production/consumption group.
    Uses load_area_energy_series under the hood.
    """
    results = []

    for area in AREA_CODES:
        df = load_area_energy_series(
            energy_type=data_type,
            area=area,
            group=group,
            start_ts=start,
            end_ts=end,
        )
        if df.empty:
            mean_val = 0.0
        else:
            m = df["kwh"].mean()
            mean_val = float(m) if pd.notna(m) else 0.0

        results.append({"area": area, "mean_value": mean_val})

    return pd.DataFrame(results)


# Optional: keep this for any other code that already imports it
@st.cache_data(show_spinner=True)
def mean_production_by_area(group: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Backwards-compatible wrapper for production only."""
    return mean_energy_by_area("Production", group, start, end)

@st.cache_data(show_spinner=True)
def get_consumption_groups() -> list[str]:
    """
    Return a sorted list of consumption groups from the consumption collection.
    """
    coll_prod, coll_cons = _get_elhub_collections()
    groups = coll_cons.distinct("consumptionGroup")
    groups = [g for g in groups if g is not None]
    return sorted(groups)


@st.cache_data(show_spinner=True)
def get_energy_groups(data_type: str) -> list[str]:
    """
    Return groups depending on energy type.
    - For 'Production': productionGroup values
    - For 'Consumption': consumptionGroup values
    """
    if data_type == "Consumption":
        return get_consumption_groups()
    return get_production_groups()

