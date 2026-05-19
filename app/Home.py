"""
Wealth Tracker — Streamlit App Entry Point
Defines navigation sections: Family Portfolio and MOM.
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
        st.Page("pages/8_Bank_Accounts.py",        title="Bank Accounts",        icon="🏦"),
        st.Page("pages/9_Fixed_Deposits.py",       title="Fixed Deposits",       icon="🏛️"),
        st.Page("pages/10_Insurance.py",           title="Insurance",            icon="🛡️"),
        st.Page("pages/11_MF_Recon.py",            title="MF Recon",             icon="🔁"),
        st.Page("pages/12_Equity_Recon.py",        title="Equity Recon",         icon="🔍"),
    ],
    "MOM": [
        st.Page("pages/MOM/1_Dashboard.py",         title="Dashboard",         icon="📊"),
        st.Page("pages/MOM/2_India_Equity.py",      title="India Equity",      icon="📈"),
        st.Page("pages/MOM/3_Mutual_Funds.py",      title="Mutual Funds",      icon="📊"),
        st.Page("pages/MOM/4_Bank_Accounts.py",     title="Bank Accounts",     icon="🏦"),
        st.Page("pages/MOM/5_Fixed_Deposits.py",    title="Fixed Deposits",    icon="🏛️"),
        st.Page("pages/MOM/6_Portfolio_History.py", title="Portfolio History", icon="📅"),
        st.Page("pages/MOM/7_MF_Recon.py",         title="MF Recon",          icon="🔁"),
        st.Page("pages/MOM/8_Equity_Recon.py",     title="Equity Recon",      icon="🔍"),
    ],
})
pg.run()
