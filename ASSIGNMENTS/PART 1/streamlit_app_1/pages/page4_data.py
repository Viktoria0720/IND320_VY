import streamlit as st

st.title("Motivation")

# Apply custom CSS for background and full-page text
st.markdown(
    """
    <style>
    .full-page {
        background-color: #1E90FF;  /* Blue background */
        color: white;                /* White text */
        height: 80vh;                /* Make it fill most of the page */
        display: flex;
        justify-content: center;     /* Center horizontally */
        align-items: center;         /* Center vertically */
        font-size: 3rem;             /* Large text */
        text-align: center;
        border-radius: 10px;         /* Optional: rounded edges */
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
