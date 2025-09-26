# app.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# -------------------------------
# CACHE THE DATA LOADING FUNCTION
# -------------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("open-meteo-subset.csv", parse_dates=["Date"])
    return df

df = load_data()

# -------------------------------
# SIDEBAR NAVIGATION
# -------------------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Home", "Data Table", "Plots", "Page 4"])

# -------------------------------
# PAGE 1: HOME
# -------------------------------
if page == "Home":
    st.title("Welcome to the Weather Data Explorer 🌦️")
    st.write("Buckle up, the most fascinating app is about to be opened!")

# -------------------------------
# PAGE 2: DATA TABLE + LINECHARTCOLUMN
# -------------------------------
elif page == "Data Table":
    st.title("Weather Data Table")
    st.write("Here is the first month of the dataset shown row-wise.")

    # Subset to the first month
    first_month = df[df["Date"].dt.month == df["Date"].dt.month.min()]

    # Build a table: one row per column
    # Each row has a sparkline (LineChartColumn)
    import streamlit.components.v1 as components  # fallback if needed
    from streamlit.elements import line_chart_column  # newer Streamlit API

    # Create row-wise table using Streamlit's dataframe API
    # Each row = column of original data
    with st.container():
        for col in df.columns:
            if col != "Date":
                st.write(f"### {col}")
                st.line_chart(first_month.set_index("Date")[col])

# -------------------------------
# PAGE 3: PLOTS + FILTERS
# -------------------------------
elif page == "Plots":
    st.title("Weather Data Plots")

    # Dropdown for selecting one column or all
    options = ["All columns"] + [c for c in df.columns if c != "Date"]
    column_choice = st.selectbox("Select column(s) to plot:", options)

    # Slider to select months
    months = sorted(df["Date"].dt.to_period("M").unique())
    month_selected = st.select_slider(
        "Select a month", options=months, value=months[0]
    )

    # Filter data by chosen month
    month_df = df[df["Date"].dt.to_period("M") == month_selected]

    # Plot
    fig, ax = plt.subplots(figsize=(8, 4))
    if column_choice == "All columns":
        for col in df.columns:
            if col != "Date":
                ax.plot(month_df["Date"], month_df[col], label=col)
    else:
        ax.plot(month_df["Date"], month_df[column_choice], label=column_choice)

    ax.set_title(f"Weather Data for {month_selected}")
    ax.set_xlabel("Date")
    ax.set_ylabel("Value")
    ax.legend()
    st.pyplot(fig)

# -------------------------------
# PAGE 4: DUMMY PAGE
# -------------------------------
elif page == "Page 4":
    st.title("Keep Calm and Don’t Give Up on Coding 💻")
    st.markdown(
        "<div style='background-color:blue; color:white; font-size:40px; "
        "text-align:center; padding:50px;'>"
        "Keep calm and don’t give up on coding. More pages are coming soon!"
        "</div>",
        unsafe_allow_html=True,
    )
