import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# Load CSV
@st.cache_data
def load_data():
    return pd.read_csv("open-meteo-subset.csv", parse_dates=['Date'])

df = load_data()

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
