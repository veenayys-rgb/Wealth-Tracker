"""Corporate Actions — 5-year split/bonus history for India Equity holdings."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import yfinance as yf

from utils.sidebar import render_sidebar
from utils.db      import fetch
from utils.fmt     import ind_num, parse_date

st.set_page_config(page_title="Corporate Actions | Wealth Tracker", page_icon="📋", layout="wide")
st.title("📋 Corporate Actions — India Equity")
render_sidebar()

st.caption(
    "Fetches 5-year split / bonus history from Yahoo Finance for all India Equity holdings. "
    "Compares your avg cost against the current price × ratio to determine whether each holding "
    "has already been adjusted or still needs correction."
)

# ── Load holdings + current prices ─────────────────────────────────────────────
all_holdings = fetch("cfg_equity_india")
prices_rows  = fetch("equity_india_prices")
prices       = {r["symbol"]: float(r["price"]) for r in prices_rows if r.get("price")}

sym_holders: dict[str, list[dict]] = {}
for h in all_holdings:
    sym = h.get("symbol", "").upper().strip()
    if not sym:
        continue
    sym_holders.setdefault(sym, []).append({
        "owner":    h.get("owner", "Vinay"),
        "qty":      float(h.get("qty", 0)),
        "avg_cost": float(h.get("avg_cost", 0)),
        "buy_date": h.get("buy_date", ""),
        "company":  h.get("company_name", ""),
    })

syms = sorted(sym_holders.keys())
st.info(f"{len(syms)} unique symbols across all owners.")

# ── Session-state cache ────────────────────────────────────────────────────────
for _k in ("ca_results", "ca_errors", "ca_no_action"):
    if _k not in st.session_state:
        st.session_state[_k] = None if _k == "ca_results" else []

# ── Controls ───────────────────────────────────────────────────────────────────
btn_col, clr_col, _ = st.columns([1, 1, 4])

if btn_col.button("🔍 Fetch Corporate Actions", type="primary", use_container_width=True):
    cutoff = pd.Timestamp.now(tz="UTC") - pd.DateOffset(years=5)
    rows, errors, no_action = [], [], []
    bar = st.progress(0, text="Starting…")

    for i, sym in enumerate(syms):
        bar.progress((i + 1) / len(syms), text=f"Fetching {sym}…  ({i+1}/{len(syms)})")
        try:
            splits = yf.Ticker(sym + ".NS").splits
            if splits is None or len(splits) == 0:
                no_action.append(sym)
                continue

            # Normalise index timezone
            if splits.index.tz is None:
                splits.index = splits.index.tz_localize("UTC")
            recent = splits[splits.index >= cutoff]
            if len(recent) == 0:
                no_action.append(sym)
                continue

            for ts, ratio in recent.items():
                if ratio == 1.0:
                    continue
                action_date = ts.date()

                if ratio > 1:
                    action_type = "Split / Bonus"
                    r = round(ratio)
                    effect = f"1 → {r} shares" if abs(ratio - r) < 0.01 else f"1 → {ratio:.3g} shares"
                    adj_hint = f"Avg cost ÷ {ratio:.3g}"
                else:
                    action_type = "Consolidation"
                    r = round(1 / ratio)
                    effect = f"{r} → 1 share" if abs((1/ratio) - r) < 0.01 else f"{1/ratio:.3g} → 1 share"
                    adj_hint = f"Avg cost × {1/ratio:.3g}"

                company = sym_holders[sym][0].get("company", "") or sym

                for h in sym_holders[sym]:
                    bd        = parse_date(h["buy_date"])
                    avg_cost  = h["avg_cost"]
                    cur_price = prices.get(sym, 0)
                    adj_cost  = avg_cost / ratio if ratio > 1 else avg_cost * ratio

                    if bd is None:
                        status = "❓ No buy date"
                    elif bd >= action_date:
                        status = "✅ Bought after — no action needed"
                    else:
                        # Bought before the action — use price comparison to infer
                        # whether avg_cost has already been adjusted.
                        # p = avg_cost / cur_price; if p ≈ ratio → cost looks pre-split.
                        if cur_price > 0 and avg_cost > 0:
                            p     = avg_cost / cur_price
                            adj_p = adj_cost / cur_price
                            if ratio > 1:
                                # Pre-split signal: avg_cost is ≈ ratio× current price
                                # AND the adjusted value would be reasonable (adj_p < 1.5)
                                if p >= ratio * 0.7 and adj_p < 1.5:
                                    status = "🔴 Pre-split — avg cost not yet adjusted"
                                elif p < ratio * 0.7:
                                    status = "🟢 Looks adjusted — avg cost in post-split range"
                                else:
                                    status = "🟡 Uncertain — manual check needed"
                            else:
                                # Consolidation: avg_cost should have risen
                                if p <= ratio * 1.3 and adj_p > 1:
                                    status = "🔴 Pre-consolidation — avg cost not yet adjusted"
                                else:
                                    status = "🟡 Uncertain — manual check needed"
                        else:
                            status = "⚠️ Bought before — no price data to verify"

                    rows.append({
                        "Status":        status,
                        "Symbol":        sym,
                        "Company":       company,
                        "Action Date":   action_date,
                        "Type":          action_type,
                        "Ratio":         ratio,
                        "Effect":        effect,
                        "Adj Hint":      adj_hint,
                        "Owner":         h["owner"],
                        "Buy Date":      bd,
                        "Current Qty":   h["qty"],
                        "Avg Cost (₹)":  avg_cost,
                        "Cur Price (₹)": cur_price if cur_price > 0 else None,
                        "Adj Cost (₹)":  round(adj_cost, 2),
                    })
        except Exception as exc:
            errors.append(f"{sym}: {exc}")

    bar.empty()
    st.session_state["ca_results"]   = rows
    st.session_state["ca_errors"]    = errors
    st.session_state["ca_no_action"] = no_action
    st.rerun()

if clr_col.button("🗑️ Clear", use_container_width=True):
    st.session_state["ca_results"]   = None
    st.session_state["ca_errors"]    = []
    st.session_state["ca_no_action"] = []
    st.rerun()

# ── Display results ────────────────────────────────────────────────────────────
results = st.session_state["ca_results"]

if results is not None:
    if results:
        pre_split = [r for r in results if r["Status"].startswith("🔴")]
        uncertain = [r for r in results if r["Status"].startswith("🟡") or r["Status"].startswith("⚠️")]
        adj_ok    = [r for r in results if r["Status"].startswith("🟢") or r["Status"].startswith("✅")]
        no_date   = [r for r in results if r["Status"].startswith("❓")]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🔴 Needs Correction", len(pre_split))
        c2.metric("🟡 Uncertain",        len(uncertain))
        c3.metric("🟢 Looks OK",         len(adj_ok))
        c4.metric("❓ No Buy Date",       len(no_date))

        def _status_rank(s):
            if s.startswith("🔴"): return 0
            if s.startswith("🟡") or s.startswith("⚠️"): return 1
            if s.startswith("🟢") or s.startswith("✅"): return 2
            return 3

        df = pd.DataFrame(results)
        df["_sort"] = df["Status"].apply(_status_rank)
        df = df.sort_values(["_sort", "Action Date"], ascending=[True, False]).drop(columns=["_sort"])

        def _row_style(row):
            s = row["Status"]
            if s.startswith("🔴"):
                bg = "background-color:#f8d7da"   # red-tint
            elif s.startswith("🟡") or s.startswith("⚠️"):
                bg = "background-color:#fff3cd"   # amber
            elif s.startswith("🟢") or s.startswith("✅"):
                bg = "background-color:#d4edda"   # green
            else:
                bg = "background-color:#f8f9fa"   # grey
            return [bg] * len(row)

        st.dataframe(
            df.style.apply(_row_style, axis=1),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Ratio":         st.column_config.NumberColumn("Ratio",         format="%.4g×"),
                "Action Date":   st.column_config.DateColumn( "Action Date",    format="DD-MMM-YYYY"),
                "Buy Date":      st.column_config.DateColumn( "Buy Date",       format="DD-MMM-YYYY"),
                "Current Qty":   st.column_config.NumberColumn("Current Qty",   format="%.2f"),
                "Avg Cost (₹)":  st.column_config.NumberColumn("Avg Cost (₹)",  format="₹%.2f"),
                "Cur Price (₹)": st.column_config.NumberColumn("Cur Price (₹)", format="₹%.2f"),
                "Adj Cost (₹)":  st.column_config.NumberColumn("Adj Cost (₹)",  format="₹%.2f",
                                    help="What avg cost should be after applying the action ratio"),
            },
        )

        st.info(
            "💡 **🔴 rows** — avg cost appears pre-split (≈ ratio × current price). "
            "Go to **India Equity → 📝 Transactions** and add a **BONUS** or **SPLIT** entry "
            "to auto-recalculate avg cost.  \n"
            "💡 **🟡 rows** — bought before the action but price has moved too much to determine "
            "from current price alone; compare *Avg Cost* vs *Adj Cost* and decide manually.  \n"
            "💡 **🟢 rows** — avg cost already looks post-split; no action needed."
        )
    else:
        st.success("✅ No corporate actions found in the last 5 years for any of your holdings.")

    errors    = st.session_state["ca_errors"]
    no_action = st.session_state["ca_no_action"]

    if no_action:
        with st.expander(f"ℹ️ {len(no_action)} symbols — no actions in 5 years"):
            st.write("  ".join(no_action))

    if errors:
        with st.expander(f"⚠️ {len(errors)} symbols could not be fetched"):
            for e in errors:
                st.caption(e)
