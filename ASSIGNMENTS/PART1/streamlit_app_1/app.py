"""
Created on Wed Sep  24 10:58:08 2023

@author: viyav
"""

import os
import datetime as dt
from typing import List, Tuple

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# Optional viz libs for the new page
try:
    import altair as alt
    USE_ALTAIR = True
except Exception:
    USE_ALTAIR = False
    alt = None
    try:
        import plotly.express as px
    except Exception:
        px = None

st.set_page_config(
    page_title="My App",
    layout="wide",                      # <<< makes the content area wide
    initial_sidebar_state="expanded"    # optional
)
# ===============================
# common data from CSV
# ===============================
@st.cache_data
def load_data():
    file_path = os.path.join(os.path.dirname(__file__), "open-meteo-subset.csv")
    df = pd.read_csv(file_path, parse_dates=["time"])
    return df

df = load_data()

# ===============================
# Functions for Elhub (Mongo) page
# ===============================
def _mongo_available() -> bool:
    try:
        _ = st.secrets["mongo"]["uri"]
        _ = st.secrets["mongo"]["db"]
        _ = st.secrets["mongo"]["collection"]
        return True
    except Exception:
        return False

@st.cache_resource(show_spinner=False)
def _get_mongo_collection():
    """Connect to MongoDB Atlas using st.secrets."""
    from pymongo import MongoClient
    import certifi

    uri = st.secrets["mongo"]["uri"]
    db_name = st.secrets["mongo"]["db"]
    coll_name = st.secrets["mongo"]["collection"]

    client = MongoClient(uri, tls=True, tlsCAFile=certifi.where())
    db = client[db_name]
    return db[coll_name]

@st.cache_data(show_spinner=False)
def _list_price_areas() -> List[str]:
    coll = _get_mongo_collection()
    areas = sorted([a for a in coll.distinct("priceArea") if a])
    return areas

@st.cache_data(show_spinner=False)
def _list_groups(price_area: str | None = None) -> List[str]:
    coll = _get_mongo_collection()
    query = {"priceArea": price_area} if price_area else {}
    groups = coll.distinct("productionGroup", filter=query)
    return sorted([g for g in groups if g])

@st.cache_data(show_spinner=False)
def _list_year_months(price_area: str | None = None) -> List[Tuple[int, int]]:
    coll = _get_mongo_collection()
    match = {"priceArea": price_area} if price_area else {}
    pipeline = [
        {"$match": match},
        {"$project": {"_id": 0, "y": {"$year": "$startTime"}, "m": {"$month": "$startTime"}}},
        {"$group": {"_id": {"y": "$y", "m": "$m"}}},
    ]
    rows = list(coll.aggregate(pipeline))
    ym = sorted([(r["_id"]["y"], r["_id"]["m"]) for r in rows if r.get("_id")])
    return ym

@st.cache_data(show_spinner=True)
def _totals_for_area(price_area: str) -> pd.DataFrame:
    coll = _get_mongo_collection()
    pipeline = [
        {"$match": {"priceArea": price_area}},
        {"$group": {"_id": "$productionGroup", "quantityKwh": {"$sum": "$quantityKwh"}}},
        {"$project": {"_id": 0, "productionGroup": "$_id", "quantityKwh": 1}},
        {"$sort": {"quantityKwh": -1}},
    ]
    return pd.DataFrame(list(coll.aggregate(pipeline)))

@st.cache_data(show_spinner=True)
def _monthly_series(price_area: str, groups: List[str], year: int, month: int) -> pd.DataFrame:
    coll = _get_mongo_collection()
    start = dt.datetime(year, month, 1, tzinfo=dt.timezone.utc)
    end = (dt.datetime(year + 1, 1, 1, tzinfo=dt.timezone.utc)
           if month == 12 else dt.datetime(year, month + 1, 1, tzinfo=dt.timezone.utc))
    match = {"priceArea": price_area, "startTime": {"$gte": start, "$lt": end}}
    if groups:
        match["productionGroup"] = {"$in": groups}
    pipeline = [
        {"$match": match},
        {"$project": {"_id": 0, "productionGroup": 1, "startTime": 1, "quantityKwh": 1}},
    ]
    df = pd.DataFrame(list(coll.aggregate(pipeline)))
    if df.empty:
        return df
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["date"] = df["startTime"].dt.date
    daily = (df.groupby(["productionGroup", "date"], as_index=False)["quantityKwh"]
               .sum()
               .sort_values(["productionGroup", "date"]))
    return daily

# -------------------------------
# SIDEBAR NAVIGATION
# -------------------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Home", "Data Table", "Plots", "Elhub (Mongo)", "To be continued"]
)

# -------------------------------
# PAGE 1: HOME
# -------------------------------
if page == "Home":
    st.title("Welcome to the Weather Data Explorer 🌦️")
    st.write("Buckle up, the most fascinating app is about to be opened!")

# -------------------------------
# PAGE 2: DATA TABLE + SPARKLINES
# -------------------------------
elif page == "Data Table":
    st.title("Weather Data Table")
    st.write("First month of the dataset, row-wise sparklines per variable:")

    months = df.iloc[:, 0]
    data = df.iloc[:, 1:]

    reshaped = pd.DataFrame({
        "Variable": data.columns,
        "Trend": [data[col].tolist() for col in data.columns]
    })

    st.dataframe(
        reshaped,
        column_config={
            "Variable": st.column_config.TextColumn("Variable"),
            "Trend": st.column_config.LineChartColumn(
                "First Month Series",
                y_min=int(data.min().min()),
                y_max=int(data.max().max()),
                width="large"
            )
        },
        hide_index=True,
        use_container_width=True
    )

    # --- alternative sparkline layout
    first_month = df['time'].dt.month.min()
    df_first_month = df[df['time'].dt.month == first_month]

    col1, col2 = st.columns([1, 3])
    col1.write("**Variable**")
    col2.write("**First Month Trend**")

    for col_name in df_first_month.columns:
        if col_name == "time":
            continue
        col_left, col_right = st.columns([1, 3])
        col_left.write(col_name)
        col_right.line_chart(df_first_month.set_index("time")[[col_name]], height=200)

# -------------------------------
# PAGE 3: PLOTS + FILTERS
# -------------------------------
elif page == "Plots":
    st.title("Weather Data Plots")

    options = ["All columns"] + [c for c in df.columns if c != "time"]
    column_choice = st.selectbox("Select column(s) to plot:", options)

    months = sorted(df["time"].dt.to_period("M").unique())
    month_selected = st.select_slider("Select a month", options=months, value=months[0])

    month_df = df[df["time"].dt.to_period("M") == month_selected]

    fig, ax = plt.subplots(figsize=(8, 4))
    if column_choice == "All columns":
        for col in df.columns:
            if col != "time":
                ax.plot(month_df["time"], month_df[col], label=col)
    else:
        ax.plot(month_df["time"], month_df[column_choice], label=column_choice)

    ax.set_title(f"Weather Data for {month_selected}")
    ax.set_xlabel("time")
    ax.set_ylabel("Value")
    ax.legend()
    st.pyplot(fig)

# -------------------------------
# PAGE 4: ELHUB (MONGO) – NEW
# -------------------------------
elif page == "Elhub (Mongo)":
    st.title("Elhub – Production per Group (MongoDB)")

    # sanity checks
    if not _mongo_available():
        st.error(
            "MongoDB secrets not found. Add `.streamlit/secrets.toml` with:\n\n"
            "[mongo]\nuri = \"...\"\ndb = \"energy\"\ncollection = \"elhub_production_2021\""
        )
        st.stop()

    try:
        # Layout
        left, right = st.columns(2, gap="large")

        with left:
            st.subheader("Distribution by Production Group")
            areas = _list_price_areas()
            if not areas:
                st.warning("No price areas found in the database.")
                st.stop()
            area = st.radio("Select price area", areas, index=0, horizontal=True)

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
                                "productionGroup",
                                alt.Tooltip("quantityKwh:Q", format=",.0f", title="kWh")
                            ],
                        )
                        .properties(height=360)
                    )
                    st.altair_chart(chart, use_container_width=True)
                elif px is not None:
                    fig = px.pie(pie_df, names="productionGroup", values="quantityKwh", title=None)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.dataframe(pie_df)

        with right:
            st.subheader("Monthly Trend")
            groups_all = _list_groups(area)
            if hasattr(st, "pills"):
                selected_groups = st.pills(
                    "Production groups",
                    options=groups_all,
                    selection_mode="multi",
                    default=groups_all[:3] if len(groups_all) > 3 else groups_all
                )
            else:
                selected_groups = st.multiselect(
                    "Production groups",
                    options=groups_all,
                    default=groups_all[:3] if len(groups_all) > 3 else groups_all
                )

            ym = _list_year_months(area)
            if not ym:
                st.info("No months found for the selected area.")
            else:
                labels = [f"{y}-{m:02d}" for y, m in ym]
                label = st.selectbox("Month", labels, index=0)
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
                            )
                            .properties(height=360)
                        )
                        st.altair_chart(line, use_container_width=True)
                    elif px is not None:
                        fig2 = px.line(
                            trend_df, x="date", y="quantityKwh", color="productionGroup"
                        )
                        fig2.update_layout(xaxis_title="Date", yaxis_title="Daily Total (kWh)")
                        st.plotly_chart(fig2, use_container_width=True)
                    else:
                        st.line_chart(
                            trend_df.pivot(index="date", columns="productionGroup", values="quantityKwh")
                        )

        with st.expander("Data source"):
            st.markdown(
                "Data comes from **Elhub** (`PRODUCTION_PER_GROUP_MBA_HOUR`), "
                "ETL’d into your MongoDB Atlas collection. Times are UTC; line chart shows **daily totals**."
            )

    except ModuleNotFoundError as e:
        st.error(
            f"Missing package: `{e.name}`. Install required deps:\n\n"
            "pip install pymongo certifi altair plotly"
        )

# -------------------------------
# PAGE 5: DUMMY PAGE
# -------------------------------
elif page == "To be continued":
    st.title("Keep Calm and Don’t Give Up on Coding 💻")
    st.markdown(
        "<div style='background-color:blue; color:white; font-size:40px; "
        "text-align:center; padding:50px;'>"
        "I know Docker is hard to deal with, but it will get better soon! Hopefully..."
        "</div>",
        unsafe_allow_html=True,
    )
