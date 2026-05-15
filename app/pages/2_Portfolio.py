"""
Portfolio — Asset Allocation by Individual (Vinay / Harsh / Anusha / Combined)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
import pandas as pd
from utils.db     import fetch, get_forex
from utils.config import load
from utils.fmt    import inr

st.set_page_config(page_title="Portfolio | Wealth Tracker", page_icon="💼", layout="wide")
st.title("💼 Portfolio")
render_sidebar()

forex = get_forex()
aed   = forex.get("AED_INR", 0)
usd   = forex.get("USD_INR", 0)


def build_allocation(owner: str) -> pd.DataFrame:
    eq_prices = {r["symbol"]: float(r["price"]) for r in fetch("equity_india_prices")}
    mf_navs   = {r["isin"]: float(r["nav"])     for r in fetch("mf_navs")}

    # Equity — only Vinay has India equity currently
    eq_inv = eq_cv = 0.0
    if owner in ("Vinay", "Combined"):
        for h in load("equity_india.json"):
            qty   = float(h.get("qty", 0))
            cost  = float(h.get("avg_cost", 0))
            price = eq_prices.get(h["symbol"].upper(), 0)
            eq_inv += qty * cost
            eq_cv  += qty * price if price > 0 else qty * cost

    # MF
    mf_inv = mf_cv = 0.0
    files  = (["mutual_funds_vinay.json", "mutual_funds_harsh.json", "mutual_funds_anusha.json"]
              if owner == "Combined"
              else [f"mutual_funds_{owner.lower()}.json"])
    for fname in files:
        for h in load(fname):
            isin  = h.get("isin", "").upper()
            units = float(h.get("units", 0))
            anav  = float(h.get("avg_nav", 0))
            nav   = mf_navs.get(isin, 0)
            mf_inv += units * anav
            mf_cv  += units * nav if nav > 0 else units * anav

    # Bank India
    bank_inv = bank_cv = 0.0
    for b in load("bank_india.json"):
        if owner == "Combined" or b.get("owner") == owner:
            bank_cv += float(b.get("balance", 0))

    # Bank UAE
    uae_inv = uae_cv = 0.0
    for b in load("bank_uae.json"):
        if owner == "Combined" or b.get("owner") == owner:
            uae_cv += float(b.get("balance_aed", 0)) * aed

    # FD
    fd_inv = fd_cv = 0.0
    for fd in load("fixed_deposits.json"):
        if owner == "Combined" or fd.get("owner") == owner:
            amt  = float(fd.get("amount", 0))
            curr = fd.get("currency", "INR")
            fd_cv += amt * aed if curr == "AED" else amt

    # Insurance (surrender value)
    ins_cv = 0.0
    for p in load("insurance.json"):
        if owner == "Combined" or p.get("owner") == owner:
            sv   = float(p.get("surrender_value", 0))
            curr = p.get("currency", "INR")
            ins_cv += sv * aed if curr == "AED" else sv

    total_inv = eq_inv + mf_inv + bank_inv + uae_inv + fd_inv
    total_cv  = eq_cv  + mf_cv  + bank_cv  + uae_cv  + fd_cv + ins_cv

    rows = [
        ("Equities – NSE",   eq_inv,   eq_cv),
        ("Mutual Funds",     mf_inv,   mf_cv),
        ("Bank Accounts",    bank_inv, bank_cv),
        ("Fixed Deposits",   fd_inv,   fd_cv),
        ("Bank Account – UAE", uae_inv, uae_cv),
        ("Insurance",        0,        ins_cv),
        ("TOTAL",            total_inv, total_cv),
    ]

    data = []
    for name, inv, cv in rows:
        gl    = cv - inv
        alloc = (cv / total_cv * 100) if total_cv > 0 else 0
        data.append({
            "Asset Class":   name,
            "Invested (₹)":  inv  if inv  > 0 else None,
            "Current (₹)":   cv   if cv   > 0 else None,
            "Gain/Loss (₹)": gl   if (inv > 0 or cv > 0) else None,
            "Allocation %":  alloc,
        })
    return pd.DataFrame(data)


def show_table(owner: str):
    df  = build_allocation(owner)
    fmt = {
        "Invested (₹)":  lambda v: f"₹ {v:,.2f}" if v is not None else "—",
        "Current (₹)":   lambda v: f"₹ {v:,.2f}" if v is not None else "—",
        "Gain/Loss (₹)": lambda v: f"₹ {v:,.2f}" if v is not None else "—",
        "Allocation %":  "{:.2f}%",
    }
    st.dataframe(
        df.style
          .format(fmt)
          .map(lambda v: "color:green" if isinstance(v, float) and v >= 0 else
                              "color:red"   if isinstance(v, float) and v < 0  else "",
                    subset=["Gain/Loss (₹)"])
          .set_properties(**{"font-weight": "bold"}, subset=pd.IndexSlice[df.index[-1], :]),
        use_container_width=True,
        hide_index=True,
    )


c1, c2 = st.columns(2)
with c1:
    st.subheader("Vinay")
    show_table("Vinay")
with c2:
    st.subheader("Harsh")
    show_table("Harsh")

c3, c4 = st.columns(2)
with c3:
    st.subheader("Anusha")
    show_table("Anusha")
with c4:
    st.subheader("Combined")
    show_table("Combined")
