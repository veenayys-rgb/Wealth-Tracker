"""Watchlist — 52-week high/low monitoring. Add/Delete."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from utils.db     import fetch
from utils.config import load, save

st.set_page_config(page_title="Watchlist | Wealth Tracker", page_icon="👀", layout="wide")
st.title("👀 Watchlist")

wp        = {r["symbol"]: r for r in fetch("watchlist_prices")}
items     = load("watchlist.json")
last_fetch = list(wp.values())[0]["fetched_at"][:19].replace("T", " ") if wp else "—"
st.caption(f"Last fetched: {last_fetch} UTC")

if items:
    rows = []
    for item in items:
        sym  = item["symbol"].upper()
        data = wp.get(sym, {})
        curr = data.get("current_price", 0) or 0
        high = data.get("high_52w", 0)      or 0
        low  = data.get("low_52w", 0)       or 0
        last = data.get("last_close", 0)    or 0
        pct_from_high = ((curr - high) / high * 100) if high > 0 else 0
        pct_from_low  = ((curr - low)  / low  * 100) if low  > 0 else 0
        rows.append({
            "ISIN Number":     item.get("isin", ""),
            "Symbol":          sym,
            "Company Name":    item.get("company_name", ""),
            "Region":          item.get("region", ""),
            "Currency":        item.get("currency", ""),
            "Last Close":      last,
            "Current Price":   curr,
            "52W High":        high,
            "52W Low":         low,
            "% from 52W High": pct_from_high,
            "% from 52W Low":  pct_from_low,
        })

    df = pd.DataFrame(rows)
    fmt = {
        "Last Close":      "{:,.4f}",
        "Current Price":   "{:,.4f}",
        "52W High":        "{:,.4f}",
        "52W Low":         "{:,.4f}",
        "% from 52W High": "{:+.2f}%",
        "% from 52W Low":  "{:+.2f}%",
    }
    st.dataframe(
        df.style
          .format(fmt)
          .map(lambda v: "color:red"   if isinstance(v, float) and v < 0 else
                              "color:green" if isinstance(v, float) and v > 0 else "",
                    subset=["% from 52W High", "% from 52W Low"]),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No items in watchlist yet. Add below.")

st.divider()

REGIONS    = ["India", "UAE", "US", "UK", "Other"]
CURRENCIES = ["INR", "AED", "USD", "GBP", "EUR", "Other"]

# ── ADD ───────────────────────────────────────────────────────────────────────
with st.expander("➕ Add to Watchlist"):
    with st.form("add_watchlist"):
        c1, c2, c3 = st.columns(3)
        isin         = c1.text_input("ISIN Number")
        symbol       = c2.text_input("Symbol (e.g. RELIANCE, AAPL)")
        company_name = c3.text_input("Company Name")
        c4, c5 = st.columns(2)
        region   = c4.selectbox("Region",   REGIONS)
        currency = c5.selectbox("Currency", CURRENCIES)
        if st.form_submit_button("Add to Watchlist"):
            if not symbol.strip():
                st.error("Symbol is required.")
            else:
                items.append({
                    "isin":         isin.strip().upper(),
                    "symbol":       symbol.strip().upper(),
                    "company_name": company_name.strip(),
                    "region":       region,
                    "currency":     currency,
                })
                save("watchlist.json", items)
                st.success(f"✅ {symbol.upper()} added to watchlist.")
                st.rerun()

# ── DELETE ────────────────────────────────────────────────────────────────────
if items:
    with st.expander("🗑️ Remove from Watchlist"):
        options_d = [f"{i['symbol']} — {i.get('company_name','')} ({i.get('region','')})"
                     for i in items]
        sel_d = st.selectbox("Select item to remove", options_d, key="del_wl_sel")
        idx_d = options_d.index(sel_d)
        st.warning(f"This will permanently remove **{items[idx_d]['symbol']}** from the watchlist.")
        if st.button("Confirm Remove", key="del_wl_btn"):
            removed = items.pop(idx_d)
            save("watchlist.json", items)
            st.success(f"✅ {removed['symbol']} removed from watchlist.")
            st.rerun()
