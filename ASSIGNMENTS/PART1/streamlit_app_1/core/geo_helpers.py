# core/geo_helpers.py
import pandas as pd
import streamlit as st

from core.constants import AREAS_DF
from core.mongo_elhub import _normalize_elhub_df  # if it's not exported, we'll re-implement normalisation
from core.elhub_energy import load_area_energy_series, _get_elhub_collections, _normalize_group_name

AREA_CODES = AREAS_DF["area"].tolist()


@st.cache_data(show_spinner=True)
def get_production_groups() -> list[str]:
    """
    Return a sorted list of production groups (normalised) from the production collection.
    """
    coll_prod, _ = _get_elhub_collections()
    raw_groups = coll_prod.distinct("productionGroup")
    groups = [_normalize_group_name(g) for g in raw_groups if g is not None]
    # Deduplicate after normalisation
    return sorted(set(groups))


@st.cache_data(show_spinner=True)
def get_consumption_groups() -> list[str]:
    """
    Return a sorted list of consumption groups (normalised) from the consumption collection.
    """
    _, coll_cons = _get_elhub_collections()
    raw_groups = coll_cons.distinct("consumptionGroup")
    groups = [_normalize_group_name(g) for g in raw_groups if g is not None]
    return sorted(set(groups))


@st.cache_data(show_spinner=True)
def get_energy_groups(data_type: str) -> list[str]:
    """
    Return groups depending on energy type.
    - For 'Production': productionGroup values (normalised)
    - For 'Consumption': consumptionGroup values (normalised)
    """
    if data_type == "Consumption":
        return get_consumption_groups()
    return get_production_groups()


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
        try:
            df = load_area_energy_series(
                energy_type=data_type,
                area=area,
                group=group,
                start_ts=start,
                end_ts=end,
            )
        except Exception:
            mean_val = 0.0
        else:
            if df.empty:
                mean_val = 0.0
            else:
                m = df["kwh"].mean()
                mean_val = float(m) if pd.notna(m) else 0.0

        results.append({"area": area, "mean_value": mean_val})

    return pd.DataFrame(results)
