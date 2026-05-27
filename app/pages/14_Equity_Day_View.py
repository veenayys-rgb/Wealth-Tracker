"""Equity Day View — current vs previous trading day close, all owners."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
import pandas as pd
from utils.db     import fetch, get_forex
from utils.config import load
from utils.fmt    import ind_num, plain_num, fmt_date, utc_to_ist

st.set_page_config(page_title="Equity Day View | Wealth Tracker",
                   page_icon="📊", layout="wide")
st.title("📊 Equity Day View")
render_sidebar()

tab_india, tab_intl = st.tabs(["🇮🇳 India", "🌍 International"])


# ── India ──────────────────────────────────────────────────────────────────────
with tab_india:
    prices_rows = fetch("equity_india_prices")
    prices      = {r["symbol"]: r for r in prices_rows}

    # last fetch timestamp
    if prices_rows:
        last_fetch = utc_to_ist(max(r["fetched_at"] for r in prices_rows))
        prev_dates = [r["prev_price_date"] for r in prices_rows if r.get("prev_price_date")]
        prev_label = fmt_date(max(prev_dates)) if prev_dates else "—"
    else:
        last_fetch = "—"
        prev_label = "—"
    st.caption(f"Price as of: {last_fetch}  |  Prev Close date: {prev_label}")

    INDIA_OWNERS = [
        ("Vinay",  "equity_india_vinay.json"),
        ("Harsh",  "equity_india_harsh.json"),
        ("Anusha", "equity_india_anusha.json"),
        ("Mom",    "mom_equity_india.json"),
    ]

    rows = []
    for owner, fname in INDIA_OWNERS:
        for h in load(fname):
            sym        = h["symbol"].upper()
            qty        = float(h.get("qty", 0))
            avg_cost   = float(h.get("avg_cost", 0))
            p          = prices.get(sym, {})
            price      = float(p.get("price", 0))      if p.get("price")      else 0.0
            prev_price = float(p.get("prev_price", 0)) if p.get("prev_price") else 0.0

            invested   = qty * avg_cost
            value      = qty * price      if price      > 0 else invested
            gl         = value - invested
            day_gl     = (price - prev_price) * qty if price > 0 and prev_price > 0 else None
            day_pct    = ((price - prev_price) / prev_price * 100) \
                         if price > 0 and prev_price > 0 else None

            rows.append({
                "Owner":      owner,
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

    if rows:
        df = pd.DataFrame(rows).sort_values("Day %", ascending=False, na_position="last")

        money   = ["Invested", "Price", "Value", "G/L", "Prev Close", "Day G/L"]
        fmt_map = {c: (lambda v: ind_num(v) if v is not None else "—") for c in money}
        fmt_map["Qty"]   = lambda v: f"{v:,.2f}" if v is not None else "—"
        fmt_map["Day %"] = lambda v: f"{v:+.2f}%" if v is not None else "—"

        color_cols = ["G/L", "Day G/L", "Day %"]

        st.dataframe(
            df.style
              .format(fmt_map)
              .map(lambda v: "color:green" if isinstance(v, float) and v >= 0
                        else "color:red"   if isinstance(v, float) and v <  0
                        else "", subset=color_cols),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Company":    st.column_config.TextColumn("Company",    width="large"),
                "Owner":      st.column_config.TextColumn("Owner",      width="small"),
                "Qty":        st.column_config.TextColumn("Qty",        width="small"),
                "Invested":   st.column_config.TextColumn("Invested",   width="medium"),
                "Price":      st.column_config.TextColumn("Price",      width="medium"),
                "Value":      st.column_config.TextColumn("Value",      width="medium"),
                "G/L":        st.column_config.TextColumn("G/L",        width="medium"),
                "Prev Close": st.column_config.TextColumn("Prev Close", width="medium"),
                "Day G/L":    st.column_config.TextColumn("Day G/L",    width="medium"),
                "Day %":      st.column_config.TextColumn("Day %",      width="small"),
            },
        )

        # summary row
        total_inv  = sum(r["Invested"] for r in rows)
        total_val  = sum(r["Value"]    for r in rows)
        total_gl   = total_val - total_inv
        total_dgl  = sum(r["Day G/L"] for r in rows if r["Day G/L"] is not None)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Invested",    ind_num(total_inv))
        c2.metric("Value",       ind_num(total_val))
        c3.metric("G/L",         ind_num(total_gl))
        c4.metric("Day G/L",     ind_num(total_dgl),
                  delta=f"{(total_dgl/total_val*100):+.2f}%" if total_val > 0 else None)
    else:
        st.info("No India equity holdings found.")


# ── International ──────────────────────────────────────────────────────────────
with tab_intl:
    forex        = get_forex()
    aed          = forex.get("AED_INR", 0)
    usd          = forex.get("USD_INR", 0)

    intl_rows_raw = fetch("equity_international_prices")
    intl_prices   = {r["symbol"]: r for r in intl_rows_raw}

    if intl_rows_raw:
        last_fetch_i = utc_to_ist(max(r["fetched_at"] for r in intl_rows_raw))
        prev_dates_i = [r["prev_price_date"] for r in intl_rows_raw if r.get("prev_price_date")]
        prev_label_i = fmt_date(max(prev_dates_i)) if prev_dates_i else "—"
    else:
        last_fetch_i = "—"
        prev_label_i = "—"
    st.caption(f"Price as of: {last_fetch_i}  |  Prev Close date: {prev_label_i}  "
               f"|  AED/INR: {aed:.4f}  |  USD/INR: {usd:.4f}")

    INTL_OWNERS = [
        ("Vinay",  "equity_intl_vinay.json"),
        ("Harsh",  "equity_intl_harsh.json"),
        ("Anusha", "equity_intl_anusha.json"),
    ]

    def _fx(curr):
        if curr == "AED": return aed
        if curr == "USD": return usd
        return 1.0

    irows = []
    for owner, fname in INTL_OWNERS:
        for h in load(fname):
            sym        = h["symbol"].upper()
            qty        = float(h.get("qty", 0))
            avg_cost   = float(h.get("avg_cost", 0))
            curr       = h.get("currency", "USD")
            rate       = _fx(curr)
            p          = intl_prices.get(sym, {})
            price      = float(p.get("price", 0))      if p.get("price")      else 0.0
            prev_price = float(p.get("prev_price", 0)) if p.get("prev_price") else 0.0

            invested   = qty * avg_cost * rate
            value      = qty * price      * rate if price      > 0 else invested
            gl         = value - invested
            day_gl     = (price - prev_price) * qty * rate \
                         if price > 0 and prev_price > 0 else None
            day_pct    = ((price - prev_price) / prev_price * 100) \
                         if price > 0 and prev_price > 0 else None

            irows.append({
                "Owner":      owner,
                "Company":    h.get("company_name") or sym,
                "Ccy":        curr,
                "Qty":        qty,
                "Invested":   invested,
                "Price":      price      if price      > 0 else None,
                "Value":      value,
                "G/L":        gl,
                "Prev Close": prev_price if prev_price > 0 else None,
                "Day G/L":    day_gl,
                "Day %":      day_pct,
            })

    if irows:
        dfi = pd.DataFrame(irows).sort_values("Day %", ascending=False, na_position="last")

        inr_cols  = ["Invested", "Value", "G/L", "Day G/L"]
        lccy_cols = ["Price", "Prev Close"]   # local currency — no ₹ prefix
        fmt_i = {c: (lambda v: ind_num(v) if v is not None else "—") for c in inr_cols}
        fmt_i.update({c: (lambda v: plain_num(v) if v is not None else "—") for c in lccy_cols})
        fmt_i["Qty"]   = lambda v: f"{v:,.4f}" if v is not None else "—"
        fmt_i["Day %"] = lambda v: f"{v:+.2f}%" if v is not None else "—"

        st.dataframe(
            dfi.style
               .format(fmt_i)
               .map(lambda v: "color:green" if isinstance(v, float) and v >= 0
                         else "color:red"   if isinstance(v, float) and v <  0
                         else "", subset=["G/L", "Day G/L", "Day %"]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Company":    st.column_config.TextColumn("Company",    width="large"),
                "Owner":      st.column_config.TextColumn("Owner",      width="small"),
                "Ccy":        st.column_config.TextColumn("Ccy",        width="small"),
                "Qty":        st.column_config.TextColumn("Qty",        width="small"),
                "Invested":   st.column_config.TextColumn("Invested",   width="medium"),
                "Price":      st.column_config.TextColumn("Price",      width="medium"),
                "Value":      st.column_config.TextColumn("Value",      width="medium"),
                "G/L":        st.column_config.TextColumn("G/L",        width="medium"),
                "Prev Close": st.column_config.TextColumn("Prev Close", width="medium"),
                "Day G/L":    st.column_config.TextColumn("Day G/L",    width="medium"),
                "Day %":      st.column_config.TextColumn("Day %",      width="small"),
            },
        )

        itotal_inv = sum(r["Invested"] for r in irows)
        itotal_val = sum(r["Value"]    for r in irows)
        itotal_gl  = itotal_val - itotal_inv
        itotal_dgl = sum(r["Day G/L"] for r in irows if r["Day G/L"] is not None)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Invested",  ind_num(itotal_inv))
        c2.metric("Value",     ind_num(itotal_val))
        c3.metric("G/L",       ind_num(itotal_gl))
        c4.metric("Day G/L",   ind_num(itotal_dgl),
                  delta=f"{(itotal_dgl/itotal_val*100):+.2f}%" if itotal_val > 0 else None)
    else:
        st.info("No international equity holdings found.")
