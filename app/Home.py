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

pg = st.navigation({
    "Family Portfolio": [
        st.Page("pages/1_Dashboard.py",            title="Dashboard",            icon="📊"),
        st.Page("pages/2_Portfolio.py",            title="Portfolio",            icon="💼"),
        st.Page("pages/3_India_Equity.py",         title="India Equity",         icon="📈"),
        st.Page("pages/4_Mutual_Funds.py",         title="Mutual Funds",         icon="📊"),
        st.Page("pages/5_International_Equity.py", title="International Equity", icon="🌍"),
        st.Page("pages/6_Watchlist.py",            title="Watchlist",            icon="👀"),
        st.Page("pages/7_Portfolio_History.py",    title="Portfolio History",    icon="📅"),
        st.Page("pages/8_Dashboard_History.py",    title="Dashboard History",    icon="📸"),
        st.Page("pages/9_Bank_Accounts.py",        title="Bank Accounts",        icon="🏦"),
        st.Page("pages/10_Fixed_Deposits.py",      title="Fixed Deposits",       icon="🏛"),
        st.Page("pages/11_Insurance.py",           title="Insurance",            icon="🛡"),
        st.Page("pages/12_MF_Recon.py",            title="MF Recon",             icon="🔁"),
        st.Page("pages/13_Equity_Recon.py",        title="Equity Recon",         icon="🔍"),
        st.Page("pages/15_Corporate_Actions.py",   title="Corporate Actions",    icon="📋"),
    ],
    "MOM": [
        st.Page("pages/14_Mom_Portfolio.py",       title="Mom Portfolio",        icon="👩"),
    ],
})
pg.run()
