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

    # Extract first month of data
    first_month = df['time'].dt.month.min()
    df_first_month = df[df['time'].dt.month == first_month]

    # Prepare table data
    table_data = []
    columns_to_plot = df_first_month.columns[1:]  # skip time column

    for col in columns_to_plot:
        values = df_first_month[col].values
        row = [
            col,
            "LineChartPlaceholder"  # pretend mini-chart
        ]
        table_data.append(row)

    # Convert to DataFrame for display
    table_df = pd.DataFrame(table_data, columns=["Variable", "First Month Trend"])
    st.dataframe(table_df, use_container_width=True)

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
