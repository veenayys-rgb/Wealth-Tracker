"""International Equity — UAE (ADX) + US. Add/Edit/Delete + INR equivalent."""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from utils.db     import fetch, get_forex
from utils.config import load, save

st.set_page_config(page_title="International | Wealth Tracker", page_icon="🌍", layout="wide")
st.title("🌍 International Equity")

forex  = get_forex()
aed    = forex.get("AED_INR", 0)
usd    = forex.get("USD_INR", 0)
prices = {r["symbol"]: float(r["price"]) for r in fetch("equity_international_prices")}

fetched_rows = fetch("equity_international_prices")
last_fetch   = fetched_rows[0]["fetched_at"][:19].replace("T", " ") if fetched_rows else "—"
st.caption(f"Last fetched: {last_fetch} UTC  |  AED/INR: {aed:.4f}  |  USD/INR: {usd:.4f}")

holdings = load("equity_international.json")

# ── View table ────────────────────────────────────────────────────────────────
if holdings:
    total_inv = total_cv = 0.0
    rows = []
    for h in holdings:
        sym   = h["symbol"].upper()
        qty   = float(h.get("qty", 0))
        cost  = float(h.get("avg_cost", 0))
        curr  = h.get("currency", "USD")
        rate  = aed if curr == "AED" else usd
        price = prices.get(sym, 0)
        inv_f = qty * cost
        cv_f  = qty * price if price > 0 else inv_f
        inv_inr = inv_f * rate
        cv_inr  = cv_f  * rate
        gl_inr  = cv_inr - inv_inr
        ret     = (gl_inr / inv_inr * 100) if inv_inr > 0 else 0
        total_inv += inv_inr
        total_cv  += cv_inr
        rows.append({
            "Name": h.get("name",""), "Symbol": sym, "ISIN": h.get("isin",""),
            "Region": h.get("region",""), "Exchange": h.get("exchange",""),
            "Currency": curr, "Source": h.get("source",""), "Buy Date": h.get("buy_date",""),
            "Qty": qty, "Avg Cost (FCY)": cost, "Invested (FCY)": inv_f,
            "Current Price (FCY)": price, "Current Value (FCY)": cv_f,
            "Forex Rate": rate, "Current Value (INR)": cv_inr,
            "Gain/Loss (INR)": gl_inr, "Return %": ret, "% of Portfolio": 0.0,
        })

    total_cv_safe = total_cv if total_cv > 0 else 1
    for r in rows:
        r["% of Portfolio"] = r["Current Value (INR)"] / total_cv_safe * 100

    total_gl  = total_cv - total_inv
    total_ret = (total_gl / total_inv * 100) if total_inv > 0 else 0
    rows.append({
        "Name": "TOTAL", "Symbol": "", "ISIN": "", "Region": "", "Exchange": "",
        "Currency": "", "Source": "", "Buy Date": "", "Qty": None,
        "Avg Cost (FCY)": None, "Invested (FCY)": None, "Current Price (FCY)": None,
        "Current Value (FCY)": None, "Forex Rate": None,
        "Current Value (INR)": total_cv, "Gain/Loss (INR)": total_gl,
        "Return %": total_ret, "% of Portfolio": 100.0,
    })
    df  = pd.DataFrame(rows)
    fmt = {
        "Qty":                   lambda v: f"{v:,.0f}" if v else "—",
        "Avg Cost (FCY)":        lambda v: f"{v:,.4f}" if v else "—",
        "Invested (FCY)":        lambda v: f"{v:,.2f}" if v else "—",
        "Current Price (FCY)":   lambda v: f"{v:,.4f}" if v else "—",
        "Current Value (FCY)":   lambda v: f"{v:,.2f}" if v else "—",
        "Forex Rate":            lambda v: f"{v:,.4f}" if v else "—",
        "Current Value (INR)":   "₹ {:,.2f}",
        "Gain/Loss (INR)":       "₹ {:,.2f}",
        "Return %":              "{:+.2f}%",
        "% of Portfolio":        "{:.2f}%",
    }
    st.dataframe(
        df.style.format(fmt)
          .applymap(lambda v: "color:green" if isinstance(v, float) and v >= 0 else
                              "color:red"   if isinstance(v, float) and v <  0 else "",
                    subset=["Gain/Loss (INR)", "Return %"])
          .set_properties(**{"font-weight": "bold"}, subset=pd.IndexSlice[df.index[-1], :]),
        use_container_width=True, hide_index=True,
    )
else:
    st.info("No international holdings yet. Add below.")

st.divider()

REGIONS    = ["UAE", "US", "UK", "Other"]
CURRENCIES = ["AED", "USD", "GBP", "EUR", "Other"]
EXCHANGES  = ["ADX", "DFM", "NYSE", "NASDAQ", "LSE", "Other"]
SOURCES    = ["Market", "IPO", "DAD"]

# ── ADD ───────────────────────────────────────────────────────────────────────
with st.expander("➕ Add New Holding"):
    with st.form("add_intl"):
        c1, c2, c3 = st.columns(3)
        name   = c1.text_input("Company Name")
        symbol = c2.text_input("Symbol")
        isin   = c3.text_input("ISIN")
        c4, c5, c6 = st.columns(3)
        region   = c4.selectbox("Region",   REGIONS)
        exchange = c5.selectbox("Exchange", EXCHANGES)
        currency = c6.selectbox("Currency", CURRENCIES)
        c7, c8, c9 = st.columns(3)
        source   = c7.selectbox("Source", SOURCES)
        buy_date = c8.date_input("Buy Date", value=datetime.date.today())
        qty      = c9.number_input("Quantity", min_value=0.0, step=1.0, format="%.4f")
        avg_cost = st.number_input("Avg Cost (FCY)", min_value=0.0, step=0.01, format="%.4f")
        if st.form_submit_button("Add Holding"):
            if not symbol.strip():
                st.error("Symbol is required.")
            else:
                holdings.append({
                    "name": name.strip(), "symbol": symbol.strip().upper(),
                    "isin": isin.strip().upper(), "region": region,
                    "exchange": exchange, "currency": currency,
                    "source": source, "buy_date": str(buy_date),
                    "qty": qty, "avg_cost": avg_cost,
                })
                save("equity_international.json", holdings)
                st.success(f"✅ {symbol.upper()} added.")
                st.rerun()

# ── EDIT ──────────────────────────────────────────────────────────────────────
if holdings:
    with st.expander("✏️ Edit Holding"):
        options = [f"{h['symbol']} — {h.get('name','')} ({h.get('region','')})" for h in holdings]
        sel     = st.selectbox("Select holding", options, key="edit_intl_sel")
        idx     = options.index(sel)
        h       = holdings[idx]
        with st.form("edit_intl"):
            c1, c2, c3 = st.columns(3)
            name   = c1.text_input("Company Name", value=h.get("name",""))
            symbol = c2.text_input("Symbol",       value=h.get("symbol",""))
            isin   = c3.text_input("ISIN",         value=h.get("isin",""))
            c4, c5, c6 = st.columns(3)
            region   = c4.selectbox("Region",   REGIONS,    index=REGIONS.index(h.get("region","UAE")) if h.get("region") in REGIONS else 0)
            exchange = c5.selectbox("Exchange", EXCHANGES,  index=EXCHANGES.index(h.get("exchange","ADX")) if h.get("exchange") in EXCHANGES else 0)
            currency = c6.selectbox("Currency", CURRENCIES, index=CURRENCIES.index(h.get("currency","AED")) if h.get("currency") in CURRENCIES else 0)
            c7, c8, c9 = st.columns(3)
            source   = c7.selectbox("Source", SOURCES, index=SOURCES.index(h.get("source","Market")) if h.get("source") in SOURCES else 0)
            try:    bd = datetime.date.fromisoformat(h.get("buy_date","2024-01-01"))
            except: bd = datetime.date.today()
            buy_date = c8.date_input("Buy Date", value=bd, key="edit_intl_bd")
            qty      = c9.number_input("Quantity",      value=float(h.get("qty",0)),      min_value=0.0, step=1.0,    format="%.4f")
            avg_cost = st.number_input("Avg Cost (FCY)", value=float(h.get("avg_cost",0)), min_value=0.0, step=0.01,   format="%.4f")
            if st.form_submit_button("Save Changes"):
                holdings[idx] = {
                    "name": name.strip(), "symbol": symbol.strip().upper(),
                    "isin": isin.strip().upper(), "region": region,
                    "exchange": exchange, "currency": currency,
                    "source": source, "buy_date": str(buy_date),
                    "qty": qty, "avg_cost": avg_cost,
                }
                save("equity_international.json", holdings)
                st.success("✅ Changes saved.")
                st.rerun()

    # ── DELETE ────────────────────────────────────────────────────────────────
    with st.expander("🗑️ Delete Holding"):
        options_d = [f"{h['symbol']} — {h.get('name','')} ({h.get('region','')})" for h in holdings]
        sel_d     = st.selectbox("Select holding to delete", options_d, key="del_intl_sel")
        idx_d     = options_d.index(sel_d)
        st.warning(f"This will permanently remove **{holdings[idx_d]['symbol']}**.")
        if st.button("Confirm Delete", key="del_intl_btn"):
            removed = holdings.pop(idx_d)
            save("equity_international.json", holdings)
            st.success(f"✅ {removed['symbol']} removed.")
            st.rerun()
