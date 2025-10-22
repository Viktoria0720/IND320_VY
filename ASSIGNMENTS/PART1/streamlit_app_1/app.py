"""
Created on Wed Sep  24 10:58:08 2023

@author: viyav
"""
# app.py
"""
Complete Streamlit app:
- Home
- Data Table (CSV + sparklines)
- Plots (CSV)
- Elhub (Mongo) – distribution + monthly trend
- To be continued
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

# Optional viz engines (we fall back gracefully if missing)
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
st.set_page_config(page_title="IND320 • Data Explorer", layout="wide")
st.markdown(
    """
    <style>
    /* make page wider on large screens */
    .block-container {max-width: 1400px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# CSV HELPERS (original functionality)
# =========================================================

@st.cache_data
def load_csv_data() -> pd.DataFrame:
    """
    Load 'open-meteo-subset.csv' sitting next to this file.
    Expects a 'time' column parseable as datetime.
    """
    file_path = os.path.join(os.path.dirname(__file__), "open-meteo-subset.csv")
    df = pd.read_csv(file_path, parse_dates=["time"])
    return df

# (Load once for CSV pages)
try:
    csv_df = load_csv_data()
except Exception as e:
    csv_df = None

# =========================================================
# MONGO HELPERS (Elhub page)
# =========================================================

@st.cache_resource(show_spinner=False)
def _get_mongo_collection():
    """
    Connect to MongoDB Atlas using st.secrets.
    Expected .streamlit/secrets.toml (local) or cloud secrets:

      [mongo]
      uri = "mongodb+srv://USER:PASS@CLUSTER/?retryWrites=true&w=majority&appName=APP"
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
    """Return distinct price areas from Mongo."""
    coll = _get_mongo_collection()
    rows = coll.distinct("priceArea")
    rows = [r for r in rows if r is not None]
    return sorted(rows)


@st.cache_data(show_spinner=False)
def _totals_for_area(price_area: str) -> pd.DataFrame:
    """Sum quantityKwh by productionGroup within a price area."""
    from pymongo import DESCENDING
    coll = _get_mongo_collection()
    pipeline = [
        {"$match": {"priceArea": price_area}},
        {"$group": {"_id": "$productionGroup", "quantityKwh": {"$sum": "$quantityKwh"}}},
        {"$project": {"_id": 0, "productionGroup": "$_id", "quantityKwh": 1}},
        {"$sort": {"quantityKwh": DESCENDING}},
    ]
    return pd.DataFrame(list(coll.aggregate(pipeline)))


@st.cache_data(show_spinner=False)
def _list_groups(price_area: str) -> list[str]:
    """Distinct production groups available in a price area."""
    coll = _get_mongo_collection()
    groups = coll.distinct("productionGroup", {"priceArea": price_area})
    groups = [g for g in groups if g is not None]
    return sorted(groups)


@st.cache_data(show_spinner=False)
def _list_year_months(price_area: str) -> list[str]:
    """
    Return available months as ['YYYY-MM', ...] for a given price area.
    Handles 'time' either as BSON Date or ISO-8601 string.
    """
    from pymongo import ASCENDING
    coll = _get_mongo_collection()
    pipeline = [
        {"$match": {"priceArea": price_area}},
        {"$addFields": {
            "time_dt": {
                "$cond": [
                    {"$eq": [{"$type": "$time"}, "date"]},
                    "$time",
                    {
                        "$dateFromString": {
                            "dateString": "$time",
                            "onError": None,
                            "onNull": None
                        }
                    }
                ]
            }
        }},
        {"$match": {"time_dt": {"$ne": None}}},
        {"$group": {"_id": {"y": {"$year": "$time_dt"}, "m": {"$month": "$time_dt"}}}},
        {"$sort": {"_id.y": ASCENDING, "_id.m": ASCENDING}},
    ]
    rows = list(coll.aggregate(pipeline))
    return [f'{r["_id"]["y"]:04d}-{r["_id"]["m"]:02d}' for r in rows]


@st.cache_data(show_spinner=True)
def _monthly_series(price_area: str, groups: list[str], year: int, month: int) -> pd.DataFrame:
    """
    Aggregate daily totals per productionGroup within the selected month.
    Output columns: ['date', 'productionGroup', 'quantityKwh'].
    """
    from pymongo import ASCENDING
    coll = _get_mongo_collection()

    if not groups:
        groups = _list_groups(price_area)

    pipeline = [
        {"$match": {"priceArea": price_area, "productionGroup": {"$in": groups}}},
        {"$addFields": {
            "time_dt": {
                "$cond": [
                    {"$eq": [{"$type": "$time"}, "date"]},
                    "$time",
                    {
                        "$dateFromString": {
                            "dateString": "$time",
                            "onError": None,
                            "onNull": None
                        }
                    }
                ]
            }
        }},
        {"$match": {"time_dt": {"$ne": None}}},
        {"$addFields": {
            "ym": {"$dateToString": {"format": "%Y-%m", "date": "$time_dt"}},
            "d": {"$dateToString": {"format": "%Y-%m-%d", "date": "$time_dt"}},
        }},
        {"$match": {"ym": f"{year:04d}-{month:02d}"}},
        {"$group": {
            "_id": {"d": "$d", "g": "$productionGroup"},
            "quantityKwh": {"$sum": "$quantityKwh"},
        }},
        {"$project": {"_id": 0, "date": "$_id.d", "productionGroup": "$_id.g", "quantityKwh": 1}},
        {"$sort": {"date": ASCENDING, "productionGroup": ASCENDING}},
    ]
    return pd.DataFrame(list(coll.aggregate(pipeline)))


# =========================================================
# SIDEBAR NAVIGATION
# =========================================================

st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Home", "Data Table", "Plots", "Elhub (Mongo)", "To be continued"],
    index=0,
)

# =========================================================
# PAGES
# =========================================================

# -------------------------------
# PAGE 1: HOME
# -------------------------------
if page == "Home":
    st.title("Welcome to the Weather & Elhub Explorer 🌦️⚡")
    st.write("Buckle up, the most fascinating app is about to be opened!")

# -------------------------------
# PAGE 2: DATA TABLE + SPARKLINES
# -------------------------------
elif page == "Data Table":
    st.title("Weather Data Table")
    if csv_df is None:
        st.error("CSV failed to load. Ensure `open-meteo-subset.csv` is next to this file.")
        st.stop()

    st.write("First month of the dataset, row-wise sparklines per variable:")

    # Extract first month subset
    first_month = csv_df["time"].dt.to_period("M").min()
    df_first_month = csv_df[csv_df["time"].dt.to_period("M") == first_month]

    # Build a reshaped table for sparkline column
    data_only = df_first_month.drop(columns=["time"])
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
                y_min=float(data_only.min().min()),
                y_max=float(data_only.max().max()),
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
        c2.line_chart(df_first_month.set_index("time")[[col_name]], height=160)

# -------------------------------
# PAGE 3: PLOTS + FILTERS
# -------------------------------
elif page == "Plots":
    st.title("Weather Data Plots")
    if csv_df is None:
        st.error("CSV failed to load. Ensure `open-meteo-subset.csv` is next to this file.")
        st.stop()

    options = ["All columns"] + [c for c in csv_df.columns if c != "time"]
    column_choice = st.selectbox("Select column(s) to plot:", options)

    months = sorted(csv_df["time"].dt.to_period("M").unique())
    month_selected = st.select_slider("Select a month", options=months, value=months[0])

    month_df = csv_df[csv_df["time"].dt.to_period("M") == month_selected]

    fig, ax = plt.subplots(figsize=(8, 4))
    if column_choice == "All columns":
        for col in csv_df.columns:
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
# PAGE 4: ELHUB (MONGO)
# -------------------------------
elif page == "Elhub (Mongo)":
    st.title("Elhub – Production per Group (MongoDB)")

    # Try a small probe to show actionable errors early
    try:
        _ = _get_mongo_collection().estimated_document_count()
    except Exception as e:
        st.error(
            "Could not connect to MongoDB.\n\n"
            "• Check `.streamlit/secrets.toml` (local) or Streamlit Cloud **Secrets** have:\n"
            "  [mongo]\n  uri = \"...\"\n  db = \"energy\"\n  collection = \"elhub_production_2021\"\n"
            "• Ensure your Atlas Network Access allows this app’s IP."
        )
        with st.expander("Technical details"):
            st.exception(e)
        st.stop()

    left, right = st.columns(2, gap="large")

    with left:
        st.subheader("Distribution by Production Group")
        areas = _list_price_areas()
        if not areas:
            st.warning("No price areas found in MongoDB.")
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
                            alt.Tooltip("productionGroup:N", title="Group"),
                            alt.Tooltip("quantityKwh:Q", title="kWh", format=",.0f"),
                        ],
                    )
                    .properties(height=360)
                )
                st.altair_chart(chart, use_container_width=True)
            elif px is not None:
                fig = px.pie(pie_df, names="productionGroup", values="quantityKwh", title=None)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.dataframe(pie_df, use_container_width=True)

    with right:
        st.subheader("Monthly Trend")

        groups_all = _list_groups(area)
        if hasattr(st, "pills"):  # Streamlit >=1.39
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
                        )
                        .properties(height=360)
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

    with st.expander("Data source"):
        st.markdown(
            "Dataset: **Elhub** `PRODUCTION_PER_GROUP_MBA_HOUR` → ETL to MongoDB Atlas.\n\n"
            "- `quantityKwh` summed as shown\n"
            "- Times treated as UTC\n"
            "- Monthly chart shows **daily totals** per production group"
        )

# -------------------------------
# PAGE 5: DUMMY PAGE
# -------------------------------
elif page == "To be continued":
    st.title("Keep Calm and Don’t Give Up on Coding 💻")
    st.markdown(
        "<div style='background-color:red; color:white; font-size:40px; "
        "text-align:center; padding:50px;'>"
        "Keep calm and don’t give up on coding. More pages are coming soon!"
        "</div>",
        unsafe_allow_html=True,
    )
