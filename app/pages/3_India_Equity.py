"""India Equity — NSE/BSE holdings per owner. Display + Quick Edit + Add/Edit/Delete."""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar, refresh_india_equity_prices
import pandas as pd
from utils.db     import fetch, service_upsert
from utils.config import load, save
from utils.fmt    import ind_num, total_metrics, fmt_date, parse_date, utc_to_ist

st.set_page_config(page_title="India Equity | Wealth Tracker", page_icon="📈", layout="wide")
st.title("📈 India Equity")
render_sidebar()

prices_rows = fetch("equity_india_prices")
prices      = {r["symbol"]: float(r["price"])      for r in prices_rows if r.get("price")}
prev_prices = {r["symbol"]: float(r["prev_price"]) for r in prices_rows if r.get("prev_price")}
last_fetch  = utc_to_ist(max((r["fetched_at"] for r in prices_rows), default=None)) if prices_rows else "—"
prev_dates  = [r["prev_price_date"] for r in prices_rows if r.get("prev_price_date")]
prev_label  = fmt_date(max(prev_dates)) if prev_dates else "—"

# ── Refresh button ──────────────────────────────────────────────────────────
_rc, _cc = st.columns([1, 4])
with _rc:
    if st.button("🔄 Refresh Prices", key="refresh_india_eq", use_container_width=True):
        with st.spinner("Fetching India equity prices…"):
            _saved, _total = refresh_india_equity_prices()
        st.success(f"✅ {_saved}/{_total} prices updated")
        st.rerun()
_cc.caption(f"Last fetched: {last_fetch}  |  Prev Close: {prev_label}")

HOLDING_TYPES = ["NRE", "NRO", "Resident"]

OWNERS = [
    ("Vinay",  "equity_india_vinay.json"),
    ("Harsh",  "equity_india_harsh.json"),
    ("Anusha", "equity_india_anusha.json"),
    ("Mom",    "mom_equity_india.json"),
]

all_tabs   = st.tabs([o for o, _ in OWNERS] + ["🏠 All"])
owner_tabs = all_tabs[:len(OWNERS)]
tab_all    = all_tabs[-1]


def _day_view_india(dv_holdings, show_owner: str | None = None):
    """Render Day View table for a list of India equity holdings."""
    if not dv_holdings:
        st.info("No holdings found.")
        return
    rows = []
    for h in dv_holdings:
        sym        = h["symbol"].upper()
        qty        = float(h.get("qty", 0))
        avg_cost   = float(h.get("avg_cost", 0))
        price      = prices.get(sym, 0)
        prev_price = prev_prices.get(sym, 0)
        invested   = qty * avg_cost
        value      = qty * price if price > 0 else invested
        gl         = value - invested
        day_gl     = (price - prev_price) * qty if price > 0 and prev_price > 0 else None
        day_pct    = ((price - prev_price) / prev_price * 100) if price > 0 and prev_price > 0 else None
        row = {
            "Company":    h.get("company_name") or sym,
            "Qty":        qty,
            "Invested":   invested,
            "Price":      price      if price      > 0 else None,
            "Value":      value,
            "G/L":        gl,
            "Prev Close": prev_price if prev_price > 0 else None,
            "Day G/L":    day_gl,
            "Day %":      day_pct,
        }
        if show_owner:
            row = {"Owner": show_owner, **row}
        rows.append(row)

    df_dv  = pd.DataFrame(rows).sort_values("Day %", ascending=False, na_position="last")
    money  = ["Invested", "Price", "Value", "G/L", "Prev Close", "Day G/L"]
    fmt_dv = {c: (lambda v: ind_num(v) if v is not None else "—") for c in money}
    fmt_dv["Qty"]   = lambda v: f"{v:,.2f}" if v is not None else "—"
    fmt_dv["Day %"] = lambda v: f"{v:+.2f}%" if v is not None else "—"

    col_cfg = {
        "Company":    st.column_config.TextColumn("Company"),
        "Qty":        st.column_config.TextColumn("Qty"),
        "Invested":   st.column_config.TextColumn("Invested"),
        "Price":      st.column_config.TextColumn("Price"),
        "Value":      st.column_config.TextColumn("Value"),
        "G/L":        st.column_config.TextColumn("G/L"),
        "Prev Close": st.column_config.TextColumn("Prev Close"),
        "Day G/L":    st.column_config.TextColumn("Day G/L"),
        "Day %":      st.column_config.TextColumn("Day %"),
    }
    if show_owner:
        col_cfg = {"Owner": st.column_config.TextColumn("Owner"), **col_cfg}

    st.dataframe(
        df_dv.style.format(fmt_dv)
             .map(lambda v: "color:green" if isinstance(v, float) and v >= 0
                       else "color:red"   if isinstance(v, float) and v <  0
                       else "", subset=["G/L", "Day G/L", "Day %"]),
        use_container_width=True, hide_index=True, column_config=col_cfg,
    )
    total_inv = sum(r["Invested"] for r in rows)
    total_val = sum(r["Value"]    for r in rows)
    total_gl  = total_val - total_inv
    total_dgl = sum(r["Day G/L"] for r in rows if r["Day G/L"] is not None)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Invested", ind_num(total_inv))
    c2.metric("Value",    ind_num(total_val))
    c3.metric("G/L",      ind_num(total_gl))
    c4.metric("Day G/L",  ind_num(total_dgl),
              delta=f"{(total_dgl/total_val*100):+.2f}%" if total_val > 0 else None)


# ── Per-owner tabs ─────────────────────────────────────────────────────────────
for tab, (owner, fname) in zip(owner_tabs, OWNERS):
    with tab:
        holdings  = load(fname)
        sub_h, sub_d = st.tabs(["📋 Holdings", "📊 Day View"])

        # ── Holdings ──────────────────────────────────────────────────────────
        with sub_h:
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
                        "Buy Date":          fmt_date(h.get("buy_date", "")),
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
                    use_container_width=True, hide_index=True,
                )
                total_metrics(total_inv, total_cv)
            else:
                st.info(f"No holdings for {owner} yet. Add below.")

            st.divider()

            # ── Quick Edit ────────────────────────────────────────────────
            if holdings:
                with st.expander("✏️ Quick Edit"):
                    qe_rows = []
                    for h in holdings:
                        sym = h["symbol"].upper()
                        bd_val = parse_date(h.get("buy_date", ""))
                        qe_rows.append({
                            "☑":                 False,
                            "Symbol":            sym,
                            "Holding Type":      h.get("holding_type", "NRE"),
                            "Source":            h.get("source", "Market"),
                            "Buy Date":          bd_val,
                            "Qty":               float(h.get("qty", 0)),
                            "Avg Cost (₹)":      float(h.get("avg_cost", 0)),
                            "Current Price (₹)": prices.get(sym, 0.0),
                        })
                    edited = st.data_editor(
                        pd.DataFrame(qe_rows),
                        column_config={
                            "☑":                 st.column_config.CheckboxColumn("☑", width="small"),
                            "Symbol":            st.column_config.TextColumn(),
                            "Holding Type":      st.column_config.SelectboxColumn(options=HOLDING_TYPES),
                            "Source":            st.column_config.SelectboxColumn(options=["Market", "IPO", "DAD"]),
                            "Buy Date":          st.column_config.DateColumn(format="DD-MMM-YYYY"),
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
                            raw_bd = edited.iloc[i]["Buy Date"]
                            holdings[i]["buy_date"] = (raw_bd.isoformat() if isinstance(raw_bd, datetime.date)
                                                       else (str(raw_bd)[:10] if raw_bd else ""))
                            holdings[i]["qty"]      = float(edited.iloc[i]["Qty"])
                            holdings[i]["avg_cost"] = float(edited.iloc[i]["Avg Cost (₹)"])
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

            # ── Add ───────────────────────────────────────────────────────
            with st.expander(f"➕ Add Holding — {owner}"):
                with st.form(f"add_equity_{owner}"):
                    c1, c2, c3 = st.columns(3)
                    isin     = c1.text_input("ISIN")
                    co_name  = c2.text_input("Company Name")
                    symbol   = c3.text_input("NSE Symbol (e.g. RELIANCE)")
                    c4, c5, c6 = st.columns(3)
                    h_type   = c4.selectbox("Holding Type", HOLDING_TYPES)
                    source   = c5.selectbox("Source", ["Market", "IPO", "DAD"])
                    buy_date = c6.date_input("Buy Date", value=datetime.date.today(), format="DD/MM/YYYY")
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

            # ── Edit ──────────────────────────────────────────────────────
            if holdings:
                with st.expander(f"✏️ Edit Holding — {owner}"):
                    options = [f"{h['symbol']} — {h.get('company_name','')} ({h.get('holding_type','')})"
                               for h in holdings]
                    sel = st.selectbox("Select holding", options, key=f"edit_eq_sel_{owner}")
                    idx = options.index(sel)
                    h   = holdings[idx]
                    with st.form(f"edit_equity_{owner}"):
                        c1, c2, c3 = st.columns(3)
                        isin     = c1.text_input("ISIN",         value=h.get("isin",""))
                        co_name  = c2.text_input("Company Name", value=h.get("company_name",""))
                        symbol   = c3.text_input("Symbol",       value=h.get("symbol",""))
                        c4, c5, c6 = st.columns(3)
                        h_type   = c4.selectbox("Holding Type", HOLDING_TYPES,
                                                index=HOLDING_TYPES.index(h.get("holding_type","NRE"))
                                                if h.get("holding_type") in HOLDING_TYPES else 0)
                        source   = c5.selectbox("Source", ["Market","IPO","DAD"],
                                                index=["Market","IPO","DAD"].index(h.get("source","Market"))
                                                if h.get("source") in ["Market","IPO","DAD"] else 0)
                        buy_date = c6.date_input("Buy Date",
                                                 value=parse_date(h.get("buy_date")) or datetime.date.today(),
                                                 format="DD/MM/YYYY", key=f"edit_bd_{owner}")
                        c7, c8 = st.columns(2)
                        qty      = c7.number_input("Quantity",     value=float(h.get("qty",0)),
                                                   min_value=0.0, step=1.0,  format="%.4f")
                        avg_cost = c8.number_input("Avg Cost (₹)", value=float(h.get("avg_cost",0)),
                                                   min_value=0.0, step=0.01, format="%.2f")
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

        # ── Day View ──────────────────────────────────────────────────────────
        with sub_d:
            _day_view_india(holdings)


# ── All ───────────────────────────────────────────────────────────────────────
with tab_all:
    sub_all_h, sub_all_d = st.tabs(["📋 Holdings", "📊 Day View"])

    with sub_all_h:
        all_rows  = []
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
                use_container_width=True, hide_index=True,
            )
            total_metrics(grand_inv, grand_cv)
        else:
            st.info("No India equity holdings yet.")

    with sub_all_d:
        all_dv = []
        for owner, fname in OWNERS:
            for h in load(fname):
                all_dv.append({**h, "_owner": owner})
        if not all_dv:
            st.info("No India equity holdings yet.")
        else:
            dv_rows = []
            for h in all_dv:
                sym        = h["symbol"].upper()
                qty        = float(h.get("qty", 0))
                avg_cost   = float(h.get("avg_cost", 0))
                price      = prices.get(sym, 0)
                prev_price = prev_prices.get(sym, 0)
                invested   = qty * avg_cost
                value      = qty * price if price > 0 else invested
                gl         = value - invested
                day_gl     = (price - prev_price) * qty if price > 0 and prev_price > 0 else None
                day_pct    = ((price - prev_price) / prev_price * 100) if price > 0 and prev_price > 0 else None
                dv_rows.append({
                    "Owner":      h["_owner"],
                    "Company":    h.get("company_name") or sym,
                    "Qty":        qty,
                    "Invested":   invested,
                    "Price":      price      if price      > 0 else None,
                    "Value":      value,
                    "G/L":        gl,
                    "Prev Close": prev_price if prev_price > 0 else None,
                    "Day G/L":    day_gl,
                    "Day %":      day_pct,
                })
            df_dv  = pd.DataFrame(dv_rows).sort_values("Day %", ascending=False, na_position="last")
            money  = ["Invested", "Price", "Value", "G/L", "Prev Close", "Day G/L"]
            fmt_dv = {c: (lambda v: ind_num(v) if v is not None else "—") for c in money}
            fmt_dv["Qty"]   = lambda v: f"{v:,.2f}" if v is not None else "—"
            fmt_dv["Day %"] = lambda v: f"{v:+.2f}%" if v is not None else "—"
            st.dataframe(
                df_dv.style.format(fmt_dv)
                     .map(lambda v: "color:green" if isinstance(v, float) and v >= 0
                               else "color:red"   if isinstance(v, float) and v <  0
                               else "", subset=["G/L", "Day G/L", "Day %"]),
                use_container_width=True, hide_index=True,
                column_config={
                    "Owner":      st.column_config.TextColumn("Owner"),
                    "Company":    st.column_config.TextColumn("Company"),
                    "Qty":        st.column_config.TextColumn("Qty"),
                    "Invested":   st.column_config.TextColumn("Invested"),
                    "Price":      st.column_config.TextColumn("Price"),
                    "Value":      st.column_config.TextColumn("Value"),
                    "G/L":        st.column_config.TextColumn("G/L"),
                    "Prev Close": st.column_config.TextColumn("Prev Close"),
                    "Day G/L":    st.column_config.TextColumn("Day G/L"),
                    "Day %":      st.column_config.TextColumn("Day %"),
                },
            )
            total_inv = sum(r["Invested"] for r in dv_rows)
            total_val = sum(r["Value"]    for r in dv_rows)
            total_gl  = total_val - total_inv
            total_dgl = sum(r["Day G/L"] for r in dv_rows if r["Day G/L"] is not None)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Invested", ind_num(total_inv))
            c2.metric("Value",    ind_num(total_val))
            c3.metric("G/L",      ind_num(total_gl))
            c4.metric("Day G/L",  ind_num(total_dgl),
                      delta=f"{(total_dgl/total_val*100):+.2f}%" if total_val > 0 else None)
