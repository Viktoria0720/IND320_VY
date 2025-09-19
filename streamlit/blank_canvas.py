# Import streamlit
import streamlit as st

# Add a header to the app
#st.header("A strange and complicated Streamlit app")

# Add a button with a label
#if st.button("Press me!"):
    #st.write("Oops, you got a virus!")

# Add a slider with a range from 0 to 100 in increments of 2, starting at 50
#slider_num = st.slider("Select a value", 0, 100, value=40, step=5)
#st.write("Slider value:", slider_num)


import streamlit as st

# Add a header to the app
st.header("A strange and complicated Streamlit app")

# Add a button with a label
if st.button("Press me!"):
    # Change background color and display a big message
    st.markdown(
        """
        <style>
        .stApp {
            background-color: red;
        }
        .big-text {
            font-size: 40px;
            font-weight: bold;
            color: white;
        }
        </style>
        <div class="big-text">Congratulations on getting a virus!</div>
        """,
        unsafe_allow_html=True
    )

# Add a slider with a range from 0 to 100 in increments of 2, starting at 40
slider_num = st.slider("Select a value", 0, 100, value=40, step=5)
st.write("Slider value:", slider_num)
