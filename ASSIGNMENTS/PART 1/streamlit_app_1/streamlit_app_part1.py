import streamlit as st

# Set page config
st.set_page_config(page_title="Weather Data App", layout="wide")

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Home", "Data Table", "Plots", "Other Page"])

# Navigate to selected page
if page == "Home":
    st.title("Home Page")
    st.write("Welcome to the Weather Data Streamlit app!")

elif page == "Data Table":
    # This will be implemented in page2_table.py later
    st.title("Data Table Page")
    st.write("Table showing the imported data will appear here.")

elif page == "Plots":
    # This will be implemented in page3_plot.py later
    st.title("Plots Page")
    st.write("Interactive plots will appear here.")

elif page == "To be continued":
    st.title("To be continued")
    st.write("Keep calm and don't give up on coding. More pages are coming soon! 😊")
