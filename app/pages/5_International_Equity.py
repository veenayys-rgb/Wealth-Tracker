"""International Equity — UAE (ADX) + US per owner. Display + Quick Edit + Add/Edit/Delete."""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
import pandas as pd
from utils.db     import fetch, get_forex, service_upsert
from utils.config import load, save
from utils.fmt    import ind_num, plain_num, total_metrics

st.set_page_config(page_title="International Equity | Wealth Tracker", page_icon="🌍", layout="wide")
st.title("🌍 International Equity")
render_sidebar()

forex        = get_forex()
aed          = forex.get("AED_INR", 0)
usd          = forex.get("USD_INR", 0)
prices_rows  = fetch("equity_international_prices")
prices       = {r["symbol"]: float(r["price"]) for r in prices_rows}
last_fetch   = prices_rows[0]["fetched_at"][:19].replace("T", " ") if prices_rows else "—"
st.caption(f"Last fetched: {last_fetch} UTC  |  AED/INR: {aed:.4f}  |  USD/INR: {usd:.4f}")

REGIONS    = ["UAE", "US", "UK", "Other"]
CURRENCIES = ["AED", "USD", "GBP", "EUR", "Other"]
EXCHANGES  = ["ADX", "DFM", "NYSE", "NASDAQ", "LSE", "Other"]
SOURCES    = ["Market", "IPO", "DAD"]

OWNERS = [
    ("Vinay",  "equity_intl_vinay.json"),
    ("Harsh",  "equity_intl_harsh.json"),
    ("Anusha", "equity_intl_anusha.json"),
]


def fx_rate(curr):
    return aed if curr == "AED" else usd


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
                sym     = h["symbol"].upper()
                qty     = float(h.get("qty", 0))
                cost    = float(h.get("avg_cost", 0))
                curr    = h.get("currency", "USD")
                rate    = fx_rate(curr)
                price   = prices.get(sym, 0)
                inv_f   = qty * cost
                cv_f    = qty * price if price > 0 else inv_f
                inv_inr = inv_f * rate
                cv_inr  = cv_f  * rate
                gl_inr  = cv_inr - inv_inr
                ret     = (gl_inr / inv_inr * 100) if inv_inr > 0 else 0.0
                total_inv += inv_inr
                total_cv  += cv_inr
                rows.append({
                    "Company Name":        h.get("name", "") or "—",
                    "Qty":                 qty,
                    "Avg Cost (FCY)":      cost,
                    "Invested (FCY)":      inv_f,
                    "Current Price (FCY)": price if price > 0 else None,
                    "Current Value (FCY)": cv_f,
                    "Forex Rate":          rate,
                    "Invested (INR)":      inv_inr,
                    "Current Value (INR)": cv_inr,
                    "Gain/Loss (INR)":     gl_inr,
                    "Return %":            ret,
                    "% of Portfolio":      0.0,
                    "Symbol":              sym,
                    "ISIN":                h.get("isin", "") or "—",
                    "Region":              h.get("region", "") or "—",
                    "Exchange":            h.get("exchange", "") or "—",
                    "Currency":            curr,
                    "Source":              h.get("source", "") or "—",
                    "Buy Date":            h.get("buy_date", "") or "—",
                })

            total_cv_safe = total_cv if total_cv > 0 else 1.0
            for r in rows:
                r["% of Portfolio"] = r["Current Value (INR)"] / total_cv_safe * 100

            df  = pd.DataFrame(rows)
            fmt = {
                "Qty":                 lambda v: f"{v:,.0f}" if v is not None else "—",
                "Avg Cost (FCY)":      lambda v: plain_num(v, decimals=4) if v is not None else "—",
                "Invested (FCY)":      lambda v: plain_num(v) if v is not None else "—",
                "Current Price (FCY)": lambda v: plain_num(v, decimals=4) if v is not None else "—",
                "Current Value (FCY)": lambda v: plain_num(v) if v is not None else "—",
                "Forex Rate":          lambda v: f"{v:.4f}" if v is not None else "—",
                "Invested (INR)":      lambda v: ind_num(v),
                "Current Value (INR)": lambda v: ind_num(v),
                "Gain/Loss (INR)":     lambda v: ind_num(v),
                "Return %":            lambda v: f"{v:+.2f}%" if v is not None else "—",
                "% of Portfolio":      lambda v: f"{v:.2f}%" if v is not None else "—",
            }
            st.dataframe(
                df.style
                  .format(fmt)
                  .map(lambda v: "color:green" if isinstance(v, float) and v >= 0 else
                                 "color:red"   if isinstance(v, float) and v <  0 else "",
                       subset=["Gain/Loss (INR)", "Return %"]),
                use_container_width=True,
                hide_index=True,
            )
            total_metrics(total_inv, total_cv)

            st.divider()
            chk_rows = [{"☑": False, "Symbol": h["symbol"].upper(), "Company Name": h.get("name",""), "Region": h.get("region","")} for h in holdings]
            chk_edited = st.data_editor(
                pd.DataFrame(chk_rows),
                column_config={"☑": st.column_config.CheckboxColumn("☑", width="small")},
                disabled=["Symbol", "Company Name", "Region"],
                hide_index=True, use_container_width=True, key=f"del_chk_intl_{owner}",
            )
            if st.button("🗑️ Delete Selected", key=f"del_intl_btn_{owner}"):
                sel = chk_edited[chk_edited["☑"]].index.tolist()
                if sel:
                    for j in sorted(sel, reverse=True):
                        holdings.pop(j)
                    save(fname, holdings)
                    st.success(f"✅ {len(sel)} holding(s) removed.")
                    st.rerun()
                else:
                    st.warning("Select at least one row to delete.")

        else:
            st.info(f"No international holdings for {owner} yet. Add below.")

        st.divider()

        # ── Quick Edit ────────────────────────────────────────────────────────
        if holdings:
            with st.expander("✏️ Quick Edit"):
                qe_rows = []
                for h in holdings:
                    sym = h["symbol"].upper()
                    qe_rows.append({
                        "Symbol":              sym,
                        "Company Name":        h.get("name", "") or "—",
                        "Source":              h.get("source", "Market"),
                        "Buy Date":            h.get("buy_date", ""),
                        "Qty":                 float(h.get("qty", 0)),
                        "Avg Cost (FCY)":      float(h.get("avg_cost", 0)),
                        "Current Price (FCY)": prices.get(sym, 0.0),
                    })
                edited = st.data_editor(
                    pd.DataFrame(qe_rows),
                    column_config={
                        "Symbol":              st.column_config.TextColumn(),
                        "Company Name":        st.column_config.TextColumn(width="medium"),
                        "Source":              st.column_config.SelectboxColumn(options=SOURCES),
                        "Buy Date":            st.column_config.TextColumn(),
                        "Qty":                 st.column_config.NumberColumn(format="%.4f", min_value=0.0),
                        "Avg Cost (FCY)":      st.column_config.NumberColumn(format="%.4f", min_value=0.0),
                        "Current Price (FCY)": st.column_config.NumberColumn(format="%.4f", min_value=0.0),
                    },
                    hide_index=True, use_container_width=True, key=f"qe_intl_{owner}",
                )
                if st.button("💾 Save Changes", key=f"qsave_intl_{owner}"):
                    price_rows = []
                    for i in range(len(holdings)):
                        holdings[i]["symbol"]   = str(edited.iloc[i]["Symbol"]).upper()
                        holdings[i]["name"]     = str(edited.iloc[i]["Company Name"])
                        holdings[i]["source"]   = str(edited.iloc[i]["Source"])
                        holdings[i]["buy_date"] = str(edited.iloc[i]["Buy Date"])
                        holdings[i]["qty"]      = float(edited.iloc[i]["Qty"])
                        holdings[i]["avg_cost"] = float(edited.iloc[i]["Avg Cost (FCY)"])
                        new_price = float(edited.iloc[i]["Current Price (FCY)"] or 0)
                        if new_price > 0:
                            price_rows.append({"symbol": holdings[i]["symbol"],
                                               "price": round(new_price, 4),
                                               "fetched_at": datetime.datetime.utcnow().isoformat()})
                    save(fname, holdings)
                    if price_rows:
                        deduped = list({r["symbol"]: r for r in price_rows}.values())
                        try:
                            service_upsert("equity_international_prices", deduped, conflict_col="symbol")
                        except Exception as e:
                            st.warning(f"Holdings saved but price update failed: {e}")
                    st.success("✅ Changes saved.")
                    st.rerun()

        # ── Add ───────────────────────────────────────────────────────────────
        with st.expander(f"➕ Add Holding — {owner}"):
            with st.form(f"add_intl_{owner}"):
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
                qty      = c9.number_input("Quantity",       min_value=0.0, step=1.0,  format="%.4f")
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
                        save(fname, holdings)
                        st.success(f"✅ {symbol.upper()} added.")
                        st.rerun()

        # ── Edit ──────────────────────────────────────────────────────────────
        if holdings:
            with st.expander(f"✏️ Edit Holding — {owner}"):
                options = [f"{h['symbol']} — {h.get('name','')} ({h.get('region','')})" for h in holdings]
                sel     = st.selectbox("Select holding", options, key=f"edit_intl_sel_{owner}")
                idx     = options.index(sel)
                h       = holdings[idx]
                with st.form(f"edit_intl_{owner}"):
                    c1, c2, c3 = st.columns(3)
                    name   = c1.text_input("Company Name", value=h.get("name",""))
                    symbol = c2.text_input("Symbol",       value=h.get("symbol",""))
                    isin   = c3.text_input("ISIN",         value=h.get("isin",""))
                    c4, c5, c6 = st.columns(3)
                    region   = c4.selectbox("Region",   REGIONS,
                                            index=REGIONS.index(h.get("region","UAE")) if h.get("region") in REGIONS else 0)
                    exchange = c5.selectbox("Exchange", EXCHANGES,
                                            index=EXCHANGES.index(h.get("exchange","ADX")) if h.get("exchange") in EXCHANGES else 0)
                    currency = c6.selectbox("Currency", CURRENCIES,
                                            index=CURRENCIES.index(h.get("currency","AED")) if h.get("currency") in CURRENCIES else 0)
                    c7, c8, c9 = st.columns(3)
                    source   = c7.selectbox("Source", SOURCES,
                                            index=SOURCES.index(h.get("source","Market")) if h.get("source") in SOURCES else 0)
                    try:    bd = datetime.date.fromisoformat(h.get("buy_date","2024-01-01"))
                    except: bd = datetime.date.today()
                    buy_date = c8.date_input("Buy Date", value=bd, key=f"edit_intl_bd_{owner}")
                    qty      = c9.number_input("Quantity",       value=float(h.get("qty",0)),      min_value=0.0, step=1.0,  format="%.4f")
                    avg_cost = st.number_input("Avg Cost (FCY)", value=float(h.get("avg_cost",0)), min_value=0.0, step=0.01, format="%.4f")
                    if st.form_submit_button("Save Changes"):
                        holdings[idx] = {
                            "name": name.strip(), "symbol": symbol.strip().upper(),
                            "isin": isin.strip().upper(), "region": region,
                            "exchange": exchange, "currency": currency,
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
            sym     = h["symbol"].upper()
            qty     = float(h.get("qty", 0))
            cost    = float(h.get("avg_cost", 0))
            curr    = h.get("currency", "USD")
            rate    = fx_rate(curr)
            price   = prices.get(sym, 0)
            inv_f   = qty * cost
            cv_f    = qty * price if price > 0 else inv_f
            inv_inr = inv_f * rate
            cv_inr  = cv_f  * rate
            gl_inr  = cv_inr - inv_inr
            ret     = (gl_inr / inv_inr * 100) if inv_inr > 0 else 0.0
            grand_inv += inv_inr
            grand_cv  += cv_inr
            all_rows.append({
                "Owner":               owner,
                "Company Name":        h.get("name", "") or "—",
                "Symbol":              sym,
                "Currency":            curr,
                "Qty":                 qty,
                "Avg Cost (FCY)":      cost,
                "Current Price (FCY)": price if price > 0 else None,
                "Invested (INR)":      inv_inr,
                "Current Value (INR)": cv_inr,
                "Gain/Loss (INR)":     gl_inr,
                "Return %":            ret,
                "% of Portfolio":      0.0,
            })

    if all_rows:
        safe = grand_cv if grand_cv > 0 else 1.0
        for r in all_rows:
            r["% of Portfolio"] = r["Current Value (INR)"] / safe * 100
        df  = pd.DataFrame(all_rows)
        fmt = {
            "Qty":                 lambda v: f"{v:,.0f}" if v is not None else "—",
            "Avg Cost (FCY)":      lambda v: plain_num(v, decimals=4) if v is not None else "—",
            "Current Price (FCY)": lambda v: plain_num(v, decimals=4) if v is not None else "—",
            "Invested (INR)":      lambda v: ind_num(v),
            "Current Value (INR)": lambda v: ind_num(v),
            "Gain/Loss (INR)":     lambda v: ind_num(v),
            "Return %":            lambda v: f"{v:+.2f}%" if v is not None else "—",
            "% of Portfolio":      lambda v: f"{v:.2f}%" if v is not None else "—",
        }
        st.dataframe(
            df.style
              .format(fmt)
              .map(lambda v: "color:green" if isinstance(v, float) and v >= 0 else
                             "color:red"   if isinstance(v, float) and v <  0 else "",
                   subset=["Gain/Loss (INR)", "Return %"]),
            use_container_width=True,
            hide_index=True,
        )
        total_metrics(grand_inv, grand_cv)
    else:
        st.info("No international equity holdings yet.")
