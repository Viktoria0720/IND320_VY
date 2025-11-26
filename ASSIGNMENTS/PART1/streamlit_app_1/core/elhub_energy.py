# core/elhub_energy.py
import os
from datetime import datetime
from typing import Literal

import pandas as pd
import streamlit as st
from pymongo import MongoClient
import certifi


EnergyType = Literal["Production", "Consumption"]


@st.cache_resource(show_spinner=False)
def _get_mongo_client() -> MongoClient:
    """
    Shared Mongo client. Tries st.secrets["mongo"]["uri"] first,
    then falls back to MONGO_URI env var, then localhost.
    """
    uri = ""

    if "mongo" in st.secrets:
        uri = st.secrets["mongo"].get("uri", "")
    if not uri:
        uri = os.getenv("MONGO_URI", "")

    if uri:
        return MongoClient(uri, tls=True, tlsCAFile=certifi.where())

    # Last-resort fallback (local dev)
    return MongoClient("mongodb://localhost:27017")


@st.cache_resource(show_spinner=False)
def _get_elhub_collections():
    """
    Returns (production_collection, consumption_collection)
    for your 2021–2024 Elhub datasets.
    """
    client = _get_mongo_client()

    # DB name: use secrets if available, otherwise 'energy'
    if "mongo" in st.secrets:
        db_name = st.secrets["mongo"].get("db", "energy")
    else:
        db_name = os.getenv("MONGO_DB", "energy")

    db = client[db_name]

    coll_prod = db["elhub_production_2021_2024"]
    coll_cons = db["elhub_consumption_2021_2024"]

    return coll_prod, coll_cons


# core/elhub_energy.py

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

    Uses the Mongo collections populated from the notebook:
      - elhub_production_2021_2024
      - elhub_consumption_2021_2024

    Returns a tidy DataFrame with columns ['time', 'kwh'].
    """
    coll_prod, coll_cons = _get_elhub_collections()
    coll = coll_prod if energy_type == "Production" else coll_cons

    group_field = "productionGroup" if energy_type == "Production" else "consumptionGroup"

    # Primary query: use year if present in the collection (fast path)
    year = int(start_ts.year)
    query_year = {
        "priceArea": area,
        group_field: group,
        "year": year,
    }

    docs = list(
        coll.find(
            query_year,
            {
                "_id": 0,
                "startTime": 1,
                "quantityKwh": 1,
            },
        )
    )

    # Fallback: if nothing found, try without the 'year' field
    if not docs:
        query_basic = {
            "priceArea": area,
            group_field: group,
        }
        docs = list(
            coll.find(
                query_basic,
                {
                    "_id": 0,
                    "startTime": 1,
                    "quantityKwh": 1,
                },
            )
        )

    if not docs:
        return pd.DataFrame(columns=["time", "kwh"])

    df = pd.DataFrame(docs)

    # Convert to Oslo local time and drop tz-info (so it matches date_input)
    df["time"] = (
        pd.to_datetime(df["startTime"], utc=True, errors="coerce")
        .dt.tz_convert("Europe/Oslo")
        .dt.tz_localize(None)
    )
    df["kwh"] = pd.to_numeric(df["quantityKwh"], errors="coerce")

    df = df.dropna(subset=["time", "kwh"]).sort_values("time")

    # Filter precisely to [start_ts, end_ts)
    mask = (df["time"] >= start_ts) & (df["time"] < end_ts)
    df = df.loc[mask, ["time", "kwh"]]

    return df.reset_index(drop=True)

