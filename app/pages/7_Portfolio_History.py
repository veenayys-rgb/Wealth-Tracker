"""Portfolio History — daily snapshots, most recent first."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from utils.db import fetch

st.set_page_config(page_title="History | Wealth Tracker", page_icon="📅", layout="wide")
st.title("📅 Portfolio History")

rows = fetch("portfolio_history")
if not rows:
    st.info("No history recorded yet. History is written after 3:30 PM IST on trading days.")
    st.stop()

df = pd.DataFrame(rows)
df = df.sort_values("date", ascending=False)
df["date"] = pd.to_datetime(df["date"]).dt.strftime("%d-%b-%Y")

display = df[[
    "date", "shares_invested", "shares_cv",
    "mf_inv_vinay", "mf_cv_vinay",
    "mf_inv_harsh", "mf_cv_harsh",
    "mf_inv_anusha", "mf_cv_anusha",
    "total_invested", "total_cv", "gain_loss", "return_pct",
]].rename(columns={
    "date":           "Date",
    "shares_invested": "Shares Invested",
    "shares_cv":       "Shares CV",
    "mf_inv_vinay":   "MF Invested – Vinay",
    "mf_cv_vinay":    "MF CV – Vinay",
    "mf_inv_harsh":   "MF Invested – Harsh",
    "mf_cv_harsh":    "MF CV – Harsh",
    "mf_inv_anusha":  "MF Invested – Anusha",
    "mf_cv_anusha":   "MF CV – Anusha",
    "total_invested": "Total Invested",
    "total_cv":       "Total CV",
    "gain_loss":      "Gain/Loss",
    "return_pct":     "Return %",
})

money_cols = [c for c in display.columns if c not in ("Date", "Return %")]
fmt = {c: "₹ {:,.2f}" for c in money_cols}
fmt["Return %"] = "{:+.2f}%"

st.dataframe(
    display.style
           .format(fmt)
           .map(lambda v: "color:green" if isinstance(v, float) and v >= 0 else
                               "color:red"   if isinstance(v, float) and v < 0  else "",
                     subset=["Gain/Loss", "Return %"]),
    use_container_width=True,
    hide_index=True,
)
