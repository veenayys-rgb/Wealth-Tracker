"""
Wealth Tracker — Streamlit App Entry Point
"""
import streamlit as st

st.set_page_config(
    page_title="Wealth Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("💰 Wealth Tracker")
st.markdown("Use the **sidebar** to navigate to any section.")
