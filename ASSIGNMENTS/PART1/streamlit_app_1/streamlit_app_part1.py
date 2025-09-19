import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# ------------------------------
# Load CSV with caching for speed
# ------------------------------
@st.cache_data
def load_data():
    return pd.read_csv("open-meteo-subset.csv", parse_dates=['Date'])

df = load_data()
numeric_columns = df.columns[1:]  # all except Date

# ------------------------------
# Sidebar navigation
# ------------------------------
st.set_page_config(page_title="Weather Data App", layout="wide")
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Home", "Data Table", "Plots", "Motivation"])

# ------------------------------
# Page 1: Home
# ------------------------------
if page == "Home":
    st.title("Home Page")
    st.markdown(
        """
        <h2 style='text-align: center; color: #2E86C1;'>
        Buckle up, the most fascinating app is about to be opened!
        </h2>
        """,
        unsafe_allow_html=True
    )

# ------------------------------
# Page 2: Data Table with Mini Charts
# ------------------------------
elif page == "Data Table":
    st.title("Data Table with Mini Line Charts")

    # Show table with first month of data only
    first_month = df['Date'].dt.month == df['Date'].dt.month.min()
    df_first_month = df.loc[first_month]

    # Display mini line charts for each numeric column
    for column in numeric_columns:
        st.write(f"**{column}**")                  # Column name
        st.line_chart(df_first_month[column])       # Mini chart

# ------------------------------
# Page 3: Interactive Plots
# ------------------------------
elif page == "Plots":
    st.title("Interactive Plots Page")

    # Column selection
    columns = ["All"] + list(df.columns[1:])
    selected_column = st.selectbox("Select column", columns)

    # Month range slider
    months = sorted(df['Date'].dt.month.unique())
    selected_months = st.select_slider("Select months", options=months, value=(months[0], months[0]))

    # Filter data for selected months
    df_filtered = df[df['Date'].dt.month.between(selected_months[0], selected_months[1])]

    # Plotting
    plt.figure(figsize=(12, 6))

    if selected_column == "All":
        for col in df.columns[1:]:
            plt.plot(df_filtered['Date'], df_filtered[col], label=col)
    else:
        plt.plot(df_filtered['Date'], df_filtered[selected_column], label=selected_column)

    plt.title("Weather Data Plot")
    plt.xlabel("Date")
    plt.ylabel("Value")
    plt.legend()
    plt.grid(True)
    st.pyplot(plt)

# ------------------------------
# Page 4: Motivation Page
# ------------------------------
elif page == "Motivation":
    st.title("Motivation")
    st.markdown(
        """
        <style>
        .full-page {
            background-color: #1E90FF;
            color: white;
            height: 80vh;
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 3rem;
            text-align: center;
            border-radius: 10px;
            padding: 20px;
        }
        </style>
        <div class="full-page">
            Keep calm and don't give up on coding.<br>
            More pages are coming soon!
        </div>
        """,
        unsafe_allow_html=True
    )
