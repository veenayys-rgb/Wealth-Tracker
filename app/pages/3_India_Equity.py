"""India Equity — NSE/BSE holdings with live prices + Add/Edit/Delete."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import datetime
from utils.db     import fetch
from utils.config import load, save

st.set_page_config(page_title="India Equity | Wealth Tracker", page_icon="📈", layout="wide")
st.title("📈 India Equity")

prices     = {r["symbol"]: float(r["price"]) for r in fetch("equity_india_prices")}
fetched    = fetch("equity_india_prices")
last_fetch = fetched[0]["fetched_at"][:19].replace("T", " ") if fetched else "—"
st.caption(f"Last fetched: {last_fetch} UTC")

holdings = load("equity_india.json")

# ── View table ────────────────────────────────────────────────────────────────
if holdings:
    total_inv = total_cv = 0.0
    rows = []
    for h in holdings:
        sym   = h["symbol"].upper()
        qty   = float(h.get("qty", 0))
        cost  = float(h.get("avg_cost", 0))
        price = prices.get(sym, 0)
        inv   = qty * cost
        cv    = qty * price if price > 0 else inv
        gl    = cv - inv
        ret   = (gl / inv * 100) if inv > 0 else 0
        total_inv += inv
        total_cv  += cv
        rows.append({
            "ISIN": h.get("isin", ""), "Company Name": h.get("company_name", ""),
            "Symbol": sym, "Holding Type": h.get("holding_type", ""),
            "Source": h.get("source", ""), "Buy Date": h.get("buy_date", ""),
            "Qty": qty, "Avg Cost (₹)": cost, "Invested (₹)": inv,
            "Current Price (₹)": price, "Current Value (₹)": cv,
            "Gain/Loss (₹)": gl, "Return %": ret, "% of Portfolio": 0.0,
        })

    total_cv_safe = total_cv if total_cv > 0 else 1
    for r in rows:
        r["% of Portfolio"] = r["Current Value (₹)"] / total_cv_safe * 100

    total_gl  = total_cv - total_inv
    total_ret = (total_gl / total_inv * 100) if total_inv > 0 else 0
    rows.append({
        "ISIN": "", "Company Name": "TOTAL", "Symbol": "", "Holding Type": "",
        "Source": "", "Buy Date": "", "Qty": None, "Avg Cost (₹)": None,
        "Invested (₹)": total_inv, "Current Price (₹)": None,
        "Current Value (₹)": total_cv, "Gain/Loss (₹)": total_gl,
        "Return %": total_ret, "% of Portfolio": 100.0,
    })
    df  = pd.DataFrame(rows)
    fmt = {
        "Avg Cost (₹)":      lambda v: f"₹ {v:,.2f}" if v else "—",
        "Invested (₹)":      "₹ {:,.2f}",
        "Current Price (₹)": lambda v: f"₹ {v:,.2f}" if v else "—",
        "Current Value (₹)": "₹ {:,.2f}",
        "Gain/Loss (₹)":     "₹ {:,.2f}",
        "Return %":          "{:+.2f}%",
        "% of Portfolio":    "{:.2f}%",
        "Qty":               lambda v: f"{v:,.0f}" if v else "—",
    }
    st.dataframe(
        df.style.format(fmt)
          .map(lambda v: "color:green" if isinstance(v, float) and v >= 0 else
                              "color:red"   if isinstance(v, float) and v <  0 else "",
                    subset=["Gain/Loss (₹)", "Return %"])
          .set_properties(**{"font-weight": "bold"}, subset=pd.IndexSlice[df.index[-1], :]),
        use_container_width=True, hide_index=True,
    )
else:
    st.info("No holdings yet. Add your first holding below.")

st.divider()

# ── ADD ───────────────────────────────────────────────────────────────────────
with st.expander("➕ Add New Holding"):
    with st.form("add_equity"):
        c1, c2, c3 = st.columns(3)
        isin     = c1.text_input("ISIN")
        co_name  = c2.text_input("Company Name")
        symbol   = c3.text_input("NSE Symbol (e.g. RELIANCE)")
        c4, c5, c6 = st.columns(3)
        h_type   = c4.selectbox("Holding Type", ["NRE", "NRO"])
        source   = c5.selectbox("Source", ["Market", "IPO", "DAD"])
        buy_date = c6.date_input("Buy Date", value=datetime.date.today())
        c7, c8 = st.columns(2)
        qty      = c7.number_input("Quantity", min_value=0.0, step=1.0, format="%.4f")
        avg_cost = c8.number_input("Avg Cost (₹)", min_value=0.0, step=0.01, format="%.2f")
        if st.form_submit_button("Add Holding"):
            if not symbol.strip():
                st.error("Symbol is required.")
            else:
                holdings.append({
                    "isin": isin.strip().upper(),
                    "company_name": co_name.strip(),
                    "symbol": symbol.strip().upper(),
                    "holding_type": h_type,
                    "source": source,
                    "buy_date": str(buy_date),
                    "qty": qty,
                    "avg_cost": avg_cost,
                })
                save("equity_india.json", holdings)
                st.success(f"✅ {symbol.upper()} added.")
                st.rerun()

# ── EDIT ──────────────────────────────────────────────────────────────────────
if holdings:
    with st.expander("✏️ Edit Holding"):
        options = [f"{h['symbol']} — {h.get('company_name','')} ({h.get('holding_type','')})"
                   for h in holdings]
        sel = st.selectbox("Select holding to edit", options, key="edit_eq_sel")
        idx = options.index(sel)
        h   = holdings[idx]
        with st.form("edit_equity"):
            c1, c2, c3 = st.columns(3)
            isin     = c1.text_input("ISIN",         value=h.get("isin", ""))
            co_name  = c2.text_input("Company Name",  value=h.get("company_name", ""))
            symbol   = c3.text_input("Symbol",        value=h.get("symbol", ""))
            c4, c5, c6 = st.columns(3)
            h_type   = c4.selectbox("Holding Type", ["NRE", "NRO"],
                                    index=["NRE","NRO"].index(h.get("holding_type","NRE")))
            source   = c5.selectbox("Source", ["Market","IPO","DAD"],
                                    index=["Market","IPO","DAD"].index(h.get("source","Market")))
            try:    bd = datetime.date.fromisoformat(h.get("buy_date","2024-01-01"))
            except: bd = datetime.date.today()
            buy_date = c6.date_input("Buy Date", value=bd, key="edit_bd")
            c7, c8 = st.columns(2)
            qty      = c7.number_input("Quantity",    value=float(h.get("qty",0)),
                                       min_value=0.0, step=1.0, format="%.4f")
            avg_cost = c8.number_input("Avg Cost (₹)", value=float(h.get("avg_cost",0)),
                                       min_value=0.0, step=0.01, format="%.2f")
            if st.form_submit_button("Save Changes"):
                holdings[idx] = {
                    "isin": isin.strip().upper(), "company_name": co_name.strip(),
                    "symbol": symbol.strip().upper(), "holding_type": h_type,
                    "source": source, "buy_date": str(buy_date),
                    "qty": qty, "avg_cost": avg_cost,
                }
                save("equity_india.json", holdings)
                st.success("✅ Changes saved.")
                st.rerun()

# ── DELETE ────────────────────────────────────────────────────────────────────
    with st.expander("🗑️ Delete Holding"):
        options_d = [f"{h['symbol']} — {h.get('company_name','')}" for h in holdings]
        sel_d = st.selectbox("Select holding to delete", options_d, key="del_eq_sel")
        idx_d = options_d.index(sel_d)
        st.warning(f"This will permanently remove **{holdings[idx_d]['symbol']}** from your holdings.")
        if st.button("Confirm Delete", key="del_eq_btn"):
            removed = holdings.pop(idx_d)
            save("equity_india.json", holdings)
            st.success(f"✅ {removed['symbol']} removed.")
            st.rerun()
