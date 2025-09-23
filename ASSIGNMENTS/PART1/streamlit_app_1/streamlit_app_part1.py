import streamlit as st
#import pandas as pd
import matplotlib.pyplot as plt

# ------------------------------
# Load CSV with caching for speed
# ------------------------------
@st.cache_data
def load_data():
    data_list= []
    with open("open-meteo-subset.csv", "r") as infile:
        for line in infile:
            split_lines= line.split(",")
            data_list.append(split_lines)
    #return read_csv("open-meteo-subset.csv", parse_dates=['Date'])
    return data_list

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

