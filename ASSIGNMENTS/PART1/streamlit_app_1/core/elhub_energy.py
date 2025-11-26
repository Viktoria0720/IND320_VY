# core/elhub_energy.py
import os
from typing import Literal

import pandas as pd
import streamlit as st
from pymongo import MongoClient
import certifi

EnergyType = Literal["Production", "Consumption"]


def _normalize_group_name(g: str) -> str:
    """Same normalisation as in _normalize_elhub_df in mongo_elhub.py."""
    return (
        str(g)
        .strip()
        .replace("_", " ")
        .title()
    )


@st.cache_resource(show_spinner=False)
def _get_mongo_client() -> MongoClient:
    """
    Shared Mongo client.
    Priority:
    1. st.secrets["mongo"]["uri"]
    2. MONGO_URI env var
    3. mongodb://localhost:27017
    """
    uri = ""

    if "mongo" in st.secrets:
        uri = st.secrets["mongo"].get("uri", "")

    if not uri:
        uri = os.getenv("MONGO_URI", "")

    if not uri:
        uri = "mongodb://localhost:27017"

    return MongoClient(uri, tls=True, tlsCAFile=certifi.where())


@st.cache_resource(show_spinner=False)
def _get_elhub_collections():
    """
    Returns (production_collection, consumption_collection) for the
    2021–2024 Elhub datasets.
    """
    client = _get_mongo_client()

    if "mongo" in st.secrets:
        db_name = st.secrets["mongo"].get("db", "energy")
    else:
        db_name = os.getenv("MONGO_DB", "energy") or "energy"

    db = client[db_name]

    # Adjust names if your collections are named differently:
    prod_name = os.getenv("MONGO_PROD_COLL", "elhub_production_2021_2024")
    cons_name = os.getenv("MONGO_CONS_COLL", "elhub_consumption_2021_2024")

    return db[prod_name], db[cons_name]


@st.cache_data(show_spinner=True)
def load_area_energy_series(
    energy_type: EnergyType,
    area: str,
    group: str,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> pd.DataFrame:
    """
    Load hourly energy series for one price area + group in [start_ts, end_ts).

    Uses:
      - elhub_production_2021_2024  (for Production)
      - elhub_consumption_2021_2024 (for Consumption)

    Returns a tidy DataFrame with columns ['time', 'kwh'] in local (Oslo) time.
    """
    coll_prod, coll_cons = _get_elhub_collections()
    coll = coll_prod if energy_type == "Production" else coll_cons

    # Which raw field holds the group code in Mongo
    raw_group_field = "productionGroup" if energy_type == "Production" else "consumptionGroup"

    # Convert naive Oslo times to UTC for querying 'startTime'
    start_oslo = start_ts.tz_localize("Europe/Oslo")
    end_oslo = end_ts.tz_localize("Europe/Oslo")
    start_utc = start_oslo.tz_convert("UTC")
    end_utc = end_oslo.tz_convert("UTC")

    # 👈 IMPORTANT: only filter by area + time in Mongo.
    # Group filtering is done in Python after normalisation.
    query = {
        "priceArea": area,
        "startTime": {"$gte": start_utc.to_pydatetime(), "$lt": end_utc.to_pydatetime()},
    }

    docs = list(
        coll.find(
            query,
            {
                "_id": 0,
                "startTime": 1,
                "quantityKwh": 1,
                raw_group_field: 1,
            },
        )
    )

    if not docs:
        return pd.DataFrame(columns=["time", "kwh"])

    df = pd.DataFrame(docs)

    # Time handling (local Oslo, no tz)
    df["time"] = (
        pd.to_datetime(df["startTime"], utc=True, errors="coerce")
        .dt.tz_convert("Europe/Oslo")
        .dt.tz_localize(None)
    )

    # Normalise group names to match the UI
    df["group"] = df[raw_group_field].apply(_normalize_group_name)

    df["kwh"] = pd.to_numeric(df["quantityKwh"], errors="coerce")
    df = df.dropna(subset=["time", "kwh", "group"]).sort_values("time")

    # Filter by group *after* normalisation
    df = df[df["group"] == group]

    # Extra time guard
    mask = (df["time"] >= start_ts) & (df["time"] < end_ts)
    df = df.loc[mask, ["time", "kwh"]]

    return df.reset_index(drop=True)

