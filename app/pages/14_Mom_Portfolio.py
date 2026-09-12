"""Mom Portfolio — Net Worth Summary."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
import pandas as pd
from utils.db     import fetch, get_forex
from utils.config import load
from utils.fmt    import ind_num, pct, metric_card

st.set_page_config(page_title="Mom Dashboard | Wealth Tracker", page_icon="📊", layout="wide")
st.title("📊 Mom — Dashboard")
render_sidebar()

forex = get_forex()
usd   = forex.get("USD_INR", 0)

# ── Compute totals ─────────────────────────────────────────────────────────────
eq_rows  = {r["symbol"]: r for r in fetch("equity_india_prices")}
nav_rows = {r["isin"]:   r for r in fetch("mf_navs")}
prices   = {sym: float(r["price"]) for sym, r in eq_rows.items()  if r.get("price")}
navs     = {isn: float(r["nav"])   for isn, r in nav_rows.items() if r.get("nav")}

eq_inv = eq_cv = 0.0
for h in load("mom_equity_india.json"):
    qty   = float(h.get("qty", 0))
    cost  = float(h.get("avg_cost", 0))
    price = prices.get(h.get("symbol", "").upper(), 0)
    eq_inv += qty * cost
    eq_cv  += qty * price if price > 0 else qty * cost

mf_inv = mf_cv = 0.0
for h in load("mom_mutual_funds.json"):
    units = float(h.get("units", 0))
    anav  = float(h.get("avg_nav", 0))
    nav   = navs.get(h.get("isin", "").upper(), 0)
    mf_inv += units * anav
    mf_cv  += units * nav if nav > 0 else units * anav

bank_cv = sum(float(b.get("balance", 0)) for b in load("mom_bank_india.json"))
fd_cv   = sum(float(fd.get("amount", 0)) for fd in load("mom_fixed_deposits.json"))

# Day G/L — equity + MF
day_gl = 0.0
invest_cv = 0.0
for h in load("mom_equity_india.json"):
    sym   = h.get("symbol", "").upper()
    qty   = float(h.get("qty", 0))
    r     = eq_rows.get(sym, {})
    price = float(r["price"])      if r.get("price")      else 0.0
    prev  = float(r["prev_price"]) if r.get("prev_price") else 0.0
    invest_cv += qty * price if price > 0 else 0.0
    if price > 0 and prev > 0:
        day_gl += (price - prev) * qty
for h in load("mom_mutual_funds.json"):
    isin  = h.get("isin", "").upper()
    units = float(h.get("units", 0))
    n     = nav_rows.get(isin, {})
    nav   = float(n["nav"])      if n.get("nav")      else 0.0
    prev  = float(n["prev_nav"]) if n.get("prev_nav") else 0.0
    invest_cv += units * nav if nav > 0 else 0.0
    if nav > 0 and prev > 0:
        day_gl += (nav - prev) * units

total_inv = eq_inv + mf_inv
total_cv  = eq_cv + mf_cv + bank_cv + fd_cv
gain      = total_cv - total_inv
ret_pct   = (gain  / total_inv  * 100) if total_inv  > 0 else 0
day_pct   = (day_gl / invest_cv * 100) if invest_cv > 0 else 0

# ── Summary cards ──────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.markdown(metric_card("Total Net Worth", ind_num(total_cv)),  unsafe_allow_html=True)
c2.markdown(metric_card("Total Invested",  ind_num(total_inv)), unsafe_allow_html=True)
c3.markdown(metric_card("Gain / Loss",     ind_num(gain), delta=pct(ret_pct)), unsafe_allow_html=True)
c4.markdown(metric_card("Today's G/L",     ind_num(day_gl), delta=pct(day_pct)), unsafe_allow_html=True)

st.divider()

# ── Breakdown table ────────────────────────────────────────────────────────────
st.subheader("Net Worth Breakdown")
asset_rows = [
    ("India Equity",   eq_inv, eq_cv),
    ("Mutual Funds",   mf_inv, mf_cv),
    ("Bank Accounts",  0,      bank_cv),
    ("Fixed Deposits", 0,      fd_cv),
]
data = []
for name, inv, cv in asset_rows:
    gl    = cv - inv
    ret   = (gl / inv * 100) if inv > 0 else 0
    alloc = (cv / total_cv * 100) if total_cv > 0 else 0
    data.append({
        "Asset Class":   name,
        "Invested":      ind_num(inv) if inv > 0 else "—",
        "Current Value": ind_num(cv),
        "Gain/Loss":     ind_num(gl)  if inv > 0 else "—",
        "Return %":      f"{ret:+.2f}%" if inv > 0 else "—",
        "Allocation %":  alloc,
    })

df = pd.DataFrame(data)
st.dataframe(
    df.style.format({"Allocation %": "{:.2f}%"}),
    use_container_width=True,
    hide_index=True,
)
st.caption("Bank/FD shown as INR  |  FD = principal amount")
