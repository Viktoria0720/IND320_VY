# core/mongo_elhub.py
import streamlit as st
import pandas as pd
from typing import List
from .constants import DASHBOARD_YEAR

@st.cache_resource(show_spinner=False)
def _get_mongo_collection():
    """Return the MongoDB collection for Elhub production."""
    from pymongo import MongoClient
    import certifi

    if "mongo" not in st.secrets:
        raise RuntimeError(
            "No [mongo] section in secrets. "
            "Add it to `.streamlit/secrets.toml` or Streamlit Cloud secrets."
        )

    uri = st.secrets["mongo"].get("uri")
    db_name = st.secrets["mongo"].get("db")
    coll_name = st.secrets["mongo"].get("collection")
    if not uri or not db_name or not coll_name:
        raise RuntimeError("Secrets missing one of: uri / db / collection.")
    try:
        client = MongoClient(uri, tls=True, tlsCAFile=certifi.where())
        db = client[db_name]
        return db[coll_name]
    except Exception as e:
        raise RuntimeError(f"Failed to connect to MongoDB: {e}")

def _agg(coll, pipeline):
    """Aggregate with disk spill enabled."""
    return list(coll.aggregate(pipeline, allowDiskUse=True))

@st.cache_data(show_spinner=False)
def list_price_areas() -> List[str]:
    coll = _get_mongo_collection()
    rows = coll.distinct("priceArea")
    rows = [r for r in rows if r is not None]
    return sorted(rows)

@st.cache_data(show_spinner=False)
def totals_for_area_year(price_area: str, year: int = DASHBOARD_YEAR) -> pd.DataFrame:
    """Sum quantityKwh by productionGroup for a price area in a given YEAR."""
    from pymongo import DESCENDING
    coll = _get_mongo_collection()
    pipeline = [
        {"$match": {"priceArea": price_area}},
        {"$project": {"_id": 0, "startTime": 1, "productionGroup": 1, "quantityKwh": 1}},
        {"$addFields": {
            "time_dt": {
                "$cond": [
                    {"$eq": [{"$type": "$startTime"}, "date"]},
                    "$startTime",
                    {"$dateFromString": {"dateString": "$startTime", "onError": None, "onNull": None}},
                ]
            }
        }},
        {"$match": {"time_dt": {"$ne": None}}},
        {"$match": {"$expr": {"$eq": [{"$year": "$time_dt"}, year]}}},
        {"$group": {"_id": "$productionGroup", "quantityKwh": {"$sum": "$quantityKwh"}}},
        {"$project": {"_id": 0, "productionGroup": "$_id", "quantityKwh": 1}},
        {"$sort": {"quantityKwh": DESCENDING}},
    ]
    return pd.DataFrame(_agg(coll, pipeline))

@st.cache_data(show_spinner=False)
def list_groups(price_area: str):
    coll = _get_mongo_collection()
    groups = coll.distinct("productionGroup", {"priceArea": price_area})
    groups = [g for g in groups if g is not None]
    return sorted(groups)

@st.cache_data(show_spinner=False)
def list_months_for_year(price_area: str, year: int = DASHBOARD_YEAR):
    """Return months in ['YYYY-MM', ...] for a price area and YEAR."""
    from pymongo import ASCENDING
    coll = _get_mongo_collection()
    pipeline = [
        {"$match": {"priceArea": price_area}},
        {"$project": {"_id": 0, "startTime": 1}},
        {"$addFields": {
            "time_dt": {
                "$cond": [
                    {"$eq": [{"$type": "$startTime"}, "date"]},
                    "$startTime",
                    {"$dateFromString": {"dateString": "$startTime", "onError": None, "onNull": None}},
                ]
            }
        }},
        {"$match": {"time_dt": {"$ne": None}}},
        {"$match": {"$expr": {"$eq": [{"$year": "$time_dt"}, year]}}},
        {"$group": {"_id": {"y": {"$year": "$time_dt"}, "m": {"$month": "$time_dt"}}}},
        {"$sort": {"_id.y": ASCENDING, "_id.m": ASCENDING}},
    ]
    rows = _agg(coll, pipeline)
    return [f'{r["_id"]["y"]:04d}-{r["_id"]["m"]:02d}' for r in rows]

@st.cache_data(show_spinner=True)
def monthly_series(price_area: str, groups, year: int, month: int) -> pd.DataFrame:
    """Daily totals for a given month and subset of groups."""
    from pymongo import ASCENDING
    coll = _get_mongo_collection()
    if not groups:
        groups = list_groups(price_area)

    ym = f"{year:04d}-{month:02d}"
    pipeline = [
        {"$match": {"priceArea": price_area, "productionGroup": {"$in": groups}}},
        {"$project": {
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
                    {"$dateFromString": {"dateString": "$startTime", "onError": None, "onNull": None}},
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
def elhub_available_years(price_area: str):
    coll = _get_mongo_collection()
    pipeline = [
        {"$match": {"priceArea": price_area}},
        {"$project": {"_id": 0, "startTime": 1}},
        {"$addFields": {
            "time_dt": {
                "$cond": [
                    {"$eq": [{"$type": "$startTime"}, "date"]},
                    "$startTime",
                    {"$dateFromString": {"dateString": "$startTime", "onError": None, "onNull": None}},
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
    """Load Elhub PRODUCTION for (area, year)."""
    coll = _get_mongo_collection()  # your production collection
    pipeline = [
        {"$match": {"priceArea": price_area}},
        {"$project": {
            "_id": 0,
            "startTime": 1,
            "priceArea": 1,
            "productionGroup": 1,
            "quantityKwh": 1,
        }},
        {"$addFields": {
            "time_dt": {
                "$cond": [
                    {"$eq": [{"$type": "$startTime"}, "date"]},
                    "$startTime",
                    {"$dateFromString": {"dateString": "$startTime", "onError": None, "onNull": None}},
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
    ]
    rows = _agg(coll, pipeline)
    return _normalize_elhub_df(rows, value_col_name="production")


def _normalize_elhub_df(rows, value_col_name: str) -> pd.DataFrame:
    """Internal helper to normalize Elhub docs into a common tidy DF."""
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["time"] = (
        pd.to_datetime(df["time"], errors="coerce", utc=True)
        .dt.tz_convert("Europe/Oslo")
        .dt.tz_localize(None)
    )
    df[value_col_name] = pd.to_numeric(df[value_col_name], errors="coerce")
    df["group"] = df["group"].astype(str).str.strip().str.replace("_", " ").str.title()
    df = df.dropna(subset=["time", value_col_name]).sort_values("time")
    return df[["time", "area", "group", value_col_name]]