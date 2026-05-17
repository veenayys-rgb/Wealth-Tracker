"""India Equity — NSE/BSE holdings per owner. Display + Quick Edit + Add/Edit/Delete."""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
import pandas as pd
from utils.db     import fetch, service_upsert
from utils.config import load, save
from utils.fmt    import ind_num, total_metrics

st.set_page_config(page_title="India Equity | Wealth Tracker", page_icon="📈", layout="wide")
st.title("📈 India Equity")
render_sidebar()

prices_rows = fetch("equity_india_prices")
prices      = {r["symbol"]: float(r["price"]) for r in prices_rows}
last_fetch  = prices_rows[0]["fetched_at"][:19].replace("T", " ") if prices_rows else "—"
st.caption(f"Last fetched: {last_fetch} UTC")

OWNERS = [
    ("Vinay",  "equity_india_vinay.json"),
    ("Harsh",  "equity_india_harsh.json"),
    ("Anusha", "equity_india_anusha.json"),
]

all_tabs   = st.tabs([o for o, _ in OWNERS] + ["🏠 All"])
owner_tabs = all_tabs[:len(OWNERS)]
tab_all    = all_tabs[-1]

for tab, (owner, fname) in zip(owner_tabs, OWNERS):
    with tab:
        holdings = load(fname)

        # ── Display table ─────────────────────────────────────────────────────
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
                ret   = (gl / inv * 100) if inv > 0 else 0.0
                total_inv += inv
                total_cv  += cv
                rows.append({
                    "ISIN":              h.get("isin", "") or "—",
                    "Company Name":      h.get("company_name", "") or "—",
                    "Qty":               qty,
                    "Avg Cost (₹)":      cost,
                    "Invested (₹)":      inv,
                    "Current Price (₹)": price if price > 0 else None,
                    "Current Value (₹)": cv,
                    "Gain/Loss (₹)":     gl,
                    "Return %":          ret,
                    "% of Portfolio":    0.0,
                    "Symbol":            sym,
                    "Holding Type":      h.get("holding_type", "") or "—",
                    "Source":            h.get("source", "") or "—",
                    "Buy Date":          h.get("buy_date", "") or "—",
                })

            total_cv_safe = total_cv if total_cv > 0 else 1.0
            for r in rows:
                r["% of Portfolio"] = r["Current Value (₹)"] / total_cv_safe * 100

            df  = pd.DataFrame(rows)
            fmt = {
                "Qty":               lambda v: f"{v:,.0f}" if v is not None else "—",
                "Avg Cost (₹)":      lambda v: ind_num(v) if v is not None else "—",
                "Invested (₹)":      lambda v: ind_num(v),
                "Current Price (₹)": lambda v: ind_num(v) if v is not None else "—",
                "Current Value (₹)": lambda v: ind_num(v),
                "Gain/Loss (₹)":     lambda v: ind_num(v),
                "Return %":          lambda v: f"{v:+.2f}%" if v is not None else "—",
                "% of Portfolio":    lambda v: f"{v:.2f}%" if v is not None else "—",
            }
            st.dataframe(
                df.style
                  .format(fmt)
                  .map(lambda v: "color:green" if isinstance(v, float) and v >= 0 else
                                 "color:red"   if isinstance(v, float) and v <  0 else "",
                       subset=["Gain/Loss (₹)", "Return %"]),
                use_container_width=True,
                hide_index=True,
            )
            total_metrics(total_inv, total_cv)

        else:
            st.info(f"No holdings for {owner} yet. Add below.")

        st.divider()

        # ── Quick Edit ────────────────────────────────────────────────────────
        if holdings:
            with st.expander("✏️ Quick Edit"):
                qe_rows = []
                for h in holdings:
                    sym = h["symbol"].upper()
                    qe_rows.append({
                        "☑":                 False,
                        "Symbol":            sym,
                        "Holding Type":      h.get("holding_type", "NRE"),
                        "Source":            h.get("source", "Market"),
                        "Buy Date":          h.get("buy_date", ""),
                        "Qty":               float(h.get("qty", 0)),
                        "Avg Cost (₹)":      float(h.get("avg_cost", 0)),
                        "Current Price (₹)": prices.get(sym, 0.0),
                    })
                edited = st.data_editor(
                    pd.DataFrame(qe_rows),
                    column_config={
                        "☑":                 st.column_config.CheckboxColumn("☑", width="small"),
                        "Symbol":            st.column_config.TextColumn(),
                        "Holding Type":      st.column_config.SelectboxColumn(options=["NRE", "NRO"]),
                        "Source":            st.column_config.SelectboxColumn(options=["Market", "IPO", "DAD"]),
                        "Buy Date":          st.column_config.TextColumn(),
                        "Qty":               st.column_config.NumberColumn(format="%.4f", min_value=0.0),
                        "Avg Cost (₹)":      st.column_config.NumberColumn(format="%.2f", min_value=0.0),
                        "Current Price (₹)": st.column_config.NumberColumn(format="%.4f", min_value=0.0),
                    },
                    hide_index=True, use_container_width=True, key=f"qe_equity_{owner}",
                )
                bc1, bc2 = st.columns(2)
                if bc1.button("💾 Save Changes", key=f"qsave_equity_{owner}"):
                    price_rows = []
                    for i in range(len(holdings)):
                        holdings[i]["symbol"]       = str(edited.iloc[i]["Symbol"]).upper()
                        holdings[i]["holding_type"] = str(edited.iloc[i]["Holding Type"])
                        holdings[i]["source"]       = str(edited.iloc[i]["Source"])
                        holdings[i]["buy_date"]     = str(edited.iloc[i]["Buy Date"])
                        holdings[i]["qty"]          = float(edited.iloc[i]["Qty"])
                        holdings[i]["avg_cost"]     = float(edited.iloc[i]["Avg Cost (₹)"])
                        raw_price = edited.iloc[i]["Current Price (₹)"]
                        new_price = float(raw_price) if raw_price is not None else 0.0
                        if new_price > 0:
                            price_rows.append({"symbol": holdings[i]["symbol"],
                                               "price": round(new_price, 4),
                                               "fetched_at": datetime.datetime.utcnow().isoformat()})
                    save(fname, holdings)
                    if price_rows:
                        deduped = list({r["symbol"]: r for r in price_rows}.values())
                        try:
                            service_upsert("equity_india_prices", deduped, conflict_col="symbol")
                        except Exception as e:
                            st.warning(f"Holdings saved but price update failed: {e}")
                    st.success("✅ Changes saved.")
                    st.rerun()
                if bc2.button("🗑️ Delete Selected", key=f"del_eq_btn_{owner}"):
                    sel = edited[edited["☑"]].index.tolist()
                    if sel:
                        for j in sorted(sel, reverse=True):
                            holdings.pop(j)
                        save(fname, holdings)
                        st.success(f"✅ {len(sel)} holding(s) removed.")
                        st.rerun()
                    else:
                        st.warning("Tick at least one row to delete.")

        # ── Add ───────────────────────────────────────────────────────────────
        with st.expander(f"➕ Add Holding — {owner}"):
            with st.form(f"add_equity_{owner}"):
                c1, c2, c3 = st.columns(3)
                isin     = c1.text_input("ISIN")
                co_name  = c2.text_input("Company Name")
                symbol   = c3.text_input("NSE Symbol (e.g. RELIANCE)")
                c4, c5, c6 = st.columns(3)
                h_type   = c4.selectbox("Holding Type", ["NRE", "NRO"])
                source   = c5.selectbox("Source", ["Market", "IPO", "DAD"])
                buy_date = c6.date_input("Buy Date", value=datetime.date.today())
                c7, c8 = st.columns(2)
                qty      = c7.number_input("Quantity",     min_value=0.0, step=1.0,  format="%.4f")
                avg_cost = c8.number_input("Avg Cost (₹)", min_value=0.0, step=0.01, format="%.2f")
                if st.form_submit_button("Add Holding"):
                    if not symbol.strip():
                        st.error("Symbol is required.")
                    else:
                        holdings.append({
                            "isin": isin.strip().upper(), "company_name": co_name.strip(),
                            "symbol": symbol.strip().upper(), "holding_type": h_type,
                            "source": source, "buy_date": str(buy_date),
                            "qty": qty, "avg_cost": avg_cost,
                        })
                        save(fname, holdings)
                        st.success(f"✅ {symbol.upper()} added.")
                        st.rerun()

        # ── Edit ──────────────────────────────────────────────────────────────
        if holdings:
            with st.expander(f"✏️ Edit Holding — {owner}"):
                options = [f"{h['symbol']} — {h.get('company_name','')} ({h.get('holding_type','')})"
                           for h in holdings]
                sel = st.selectbox("Select holding", options, key=f"edit_eq_sel_{owner}")
                idx = options.index(sel)
                h   = holdings[idx]
                with st.form(f"edit_equity_{owner}"):
                    c1, c2, c3 = st.columns(3)
                    isin     = c1.text_input("ISIN",          value=h.get("isin",""))
                    co_name  = c2.text_input("Company Name",  value=h.get("company_name",""))
                    symbol   = c3.text_input("Symbol",        value=h.get("symbol",""))
                    c4, c5, c6 = st.columns(3)
                    h_type   = c4.selectbox("Holding Type", ["NRE","NRO"],
                                            index=["NRE","NRO"].index(h.get("holding_type","NRE"))
                                            if h.get("holding_type") in ["NRE","NRO"] else 0)
                    source   = c5.selectbox("Source", ["Market","IPO","DAD"],
                                            index=["Market","IPO","DAD"].index(h.get("source","Market"))
                                            if h.get("source") in ["Market","IPO","DAD"] else 0)
                    try:    bd = datetime.date.fromisoformat(h.get("buy_date","2024-01-01"))
                    except: bd = datetime.date.today()
                    buy_date = c6.date_input("Buy Date", value=bd, key=f"edit_bd_{owner}")
                    c7, c8 = st.columns(2)
                    qty      = c7.number_input("Quantity",     value=float(h.get("qty",0)),      min_value=0.0, step=1.0,  format="%.4f")
                    avg_cost = c8.number_input("Avg Cost (₹)", value=float(h.get("avg_cost",0)), min_value=0.0, step=0.01, format="%.2f")
                    if st.form_submit_button("Save Changes"):
                        holdings[idx] = {
                            "isin": isin.strip().upper(), "company_name": co_name.strip(),
                            "symbol": symbol.strip().upper(), "holding_type": h_type,
                            "source": source, "buy_date": str(buy_date),
                            "qty": qty, "avg_cost": avg_cost,
                        }
                        save(fname, holdings)
                        st.success("✅ Changes saved.")
                        st.rerun()


# ── All ───────────────────────────────────────────────────────────────────────
with tab_all:
    all_rows = []
    grand_inv = grand_cv = 0.0
    for owner, fname in OWNERS:
        for h in load(fname):
            sym   = h["symbol"].upper()
            qty   = float(h.get("qty", 0))
            cost  = float(h.get("avg_cost", 0))
            price = prices.get(sym, 0)
            inv   = qty * cost
            cv    = qty * price if price > 0 else inv
            gl    = cv - inv
            ret   = (gl / inv * 100) if inv > 0 else 0.0
            grand_inv += inv
            grand_cv  += cv
            all_rows.append({
                "Owner":             owner,
                "Company Name":      h.get("company_name", "") or "—",
                "Symbol":            sym,
                "Qty":               qty,
                "Avg Cost (₹)":      cost,
                "Invested (₹)":      inv,
                "Current Price (₹)": price if price > 0 else None,
                "Current Value (₹)": cv,
                "Gain/Loss (₹)":     gl,
                "Return %":          ret,
                "% of Portfolio":    0.0,
            })

    if all_rows:
        safe = grand_cv if grand_cv > 0 else 1.0
        for r in all_rows:
            r["% of Portfolio"] = r["Current Value (₹)"] / safe * 100
        df  = pd.DataFrame(all_rows)
        fmt = {
            "Qty":               lambda v: f"{v:,.0f}" if v is not None else "—",
            "Avg Cost (₹)":      lambda v: ind_num(v) if v is not None else "—",
            "Invested (₹)":      lambda v: ind_num(v),
            "Current Price (₹)": lambda v: ind_num(v) if v is not None else "—",
            "Current Value (₹)": lambda v: ind_num(v),
            "Gain/Loss (₹)":     lambda v: ind_num(v),
            "Return %":          lambda v: f"{v:+.2f}%" if v is not None else "—",
            "% of Portfolio":    lambda v: f"{v:.2f}%" if v is not None else "—",
        }
        st.dataframe(
            df.style
              .format(fmt)
              .map(lambda v: "color:green" if isinstance(v, float) and v >= 0 else
                             "color:red"   if isinstance(v, float) and v <  0 else "",
                   subset=["Gain/Loss (₹)", "Return %"]),
            use_container_width=True,
            hide_index=True,
        )
        total_metrics(grand_inv, grand_cv)
    else:
        st.info("No India equity holdings yet.")
