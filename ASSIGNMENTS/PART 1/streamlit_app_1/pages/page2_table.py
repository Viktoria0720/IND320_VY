import streamlit as st
import pandas as pd

# Load CSV with caching for speed
@st.cache_data
def load_data():
    return pd.read_csv("open-meteo-subset.csv", parse_dates=['Date'])

df = load_data()

st.title("Data Table with Mini Line Charts")

# Show table with first month of data only
first_month = df['Date'].dt.month == df['Date'].dt.month.min()
df_first_month = df.loc[first_month]

# Iterate over numeric columns
for column in df.columns[1:]:
    st.write(f"**{column}**")                  # Column name
    st.line_chart(df_first_month[column])       # Mini line chart per column
