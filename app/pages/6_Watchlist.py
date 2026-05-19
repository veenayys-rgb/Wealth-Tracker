"""Watchlist — 52-week high/low monitoring. Add/Delete."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
import pandas as pd
from utils.db     import fetch
from utils.config import load, save

st.set_page_config(page_title="Watchlist | Wealth Tracker", page_icon="👀", layout="wide")
st.title("👀 Watchlist")
render_sidebar()

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
        chg     = curr - last
        chg_pct = (chg / last * 100) if last > 0 else 0
        rows.append({
            "ISIN Number":   item.get("isin", ""),
            "Symbol":        sym,
            "Company Name":  item.get("company_name", ""),
            "Region":        item.get("region", ""),
            "Currency":      item.get("currency", ""),
            "Last Close":    last,
            "Current Price": curr,
            "Change":        chg,
            "Change %":      chg_pct,
            "52W High":      high,
            "52W Low":       low,
        })

    df = pd.DataFrame(rows)
    fmt = {
        "Last Close":    "{:,.4f}",
        "Current Price": "{:,.4f}",
        "Change":        lambda v: f"{v:+,.4f}",
        "Change %":      lambda v: f"{v:+.2f}%",
        "52W High":      "{:,.4f}",
        "52W Low":       "{:,.4f}",
    }
    st.dataframe(
        df.style
          .format(fmt)
          .map(lambda v: "color:green" if isinstance(v, float) and v > 0 else
                         "color:red"   if isinstance(v, float) and v < 0 else "",
                    subset=["Change", "Change %"]),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    chk_rows = [{"☑": False, "Symbol": i["symbol"].upper(), "Company Name": i.get("company_name",""), "Region": i.get("region","")} for i in items]
    chk_edited = st.data_editor(
        pd.DataFrame(chk_rows),
        column_config={"☑": st.column_config.CheckboxColumn("☑", width="small")},
        disabled=["Symbol", "Company Name", "Region"],
        hide_index=True, use_container_width=True, key="del_chk_wl",
    )
    if st.button("🗑️ Delete Selected", key="del_wl_btn"):
        sel = chk_edited[chk_edited["☑"]].index.tolist()
        if sel:
            for j in sorted(sel, reverse=True):
                items.pop(j)
            save("watchlist.json", items)
            st.success(f"✅ {len(sel)} item(s) removed.")
            st.rerun()
        else:
            st.warning("Select at least one row to delete.")

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

