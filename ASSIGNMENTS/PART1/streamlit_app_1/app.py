# app.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os
from streamlit.elements import line_chart_column  

# -------------------------------
# CACHE THE DATA LOADING FUNCTION
# -------------------------------
@st.cache_data
def load_data():
    file_path = os.path.join(os.path.dirname(__file__), "open-meteo-subset.csv")
    df = pd.read_csv(file_path, parse_dates=["time"])
    return df

df = load_data()

# -------------------------------
# SIDEBAR NAVIGATION
# -------------------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Home", "Data Table", "Plots", "To be continued"])

# -------------------------------
# PAGE 1: HOME
# -------------------------------
if page == "Home":
    st.title("Welcome to the Weather Data Explorer 🌦️")
    st.write("Buckle up, the most fascinating app is about to be opened!")

# -------------------------------
# PAGE 2: DATA TABLE + SPARKLINES (placeholder)
# -------------------------------
elif page == "Data Table":
    st.title("Weather Data Table")
    st.write("Here is the first month of the dataset shown row-wise.")

    # -------------------------------
    # Extract first month of data
    # -------------------------------
    first_month = df['time'].dt.month.min()
    df_first_month = df[df['time'].dt.month == first_month]

    # -------------------------------
    # Create table header
    # -------------------------------
    col1, col2 = st.columns([1, 3])
    col1.write("**Variable**")
    col2.write("**First Month Trend**")

    # -------------------------------
    # Fill table row by row
    # -------------------------------
    for col_name in df_first_month.columns:
        if col_name == "time":
            continue  # skip time column
        col_left, col_right = st.columns([1, 3])
        col_left.write(col_name)
        # Mini sparkline chart
        col_right.line_chart(df_first_month[[col_name]], height=50)
# -------------------------------
# PAGE 3: PLOTS + FILTERS
# -------------------------------
elif page == "Plots":
    st.title("Weather Data Plots")

    # Dropdown for selecting one column or all
    options = ["All columns"] + [c for c in df.columns if c != "time"]
    column_choice = st.selectbox("Select column(s) to plot:", options)

    # Slider to select months
    months = sorted(df["time"].dt.to_period("M").unique())
    month_selected = st.select_slider("Select a month", options=months, value=months[0])

    # Filter data by chosen month
    month_df = df[df["time"].dt.to_period("M") == month_selected]

    # Plot
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
# PAGE 4: DUMMY PAGE
# -------------------------------
elif page == "To be continued":
    st.title("Keep Calm and Don’t Give Up on Coding 💻")
    st.markdown(
        "<div style='background-color:blue; color:white; font-size:40px; "
        "text-align:center; padding:50px;'>"
        "Keep calm and don’t give up on coding. More pages are coming soon!"
        "</div>",
        unsafe_allow_html=True,
    )
