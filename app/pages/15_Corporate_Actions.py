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
    "Fetches 5-year split / bonus history from Yahoo Finance for all India Equity holdings, "
    "then cross-references with your buy dates to flag holdings that may need avg cost correction."
)

# ── Load holdings ──────────────────────────────────────────────────────────────
all_holdings = fetch("cfg_equity_india")

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
                    bd = parse_date(h["buy_date"])
                    if bd is None:
                        status = "❓ No buy date"
                    elif bd < action_date:
                        status = "⚠️ Bought before — verify avg cost"
                    else:
                        status = "✅ Bought after — likely OK"

                    rows.append({
                        "Status":       status,
                        "Symbol":       sym,
                        "Company":      company,
                        "Action Date":  action_date,
                        "Type":         action_type,
                        "Ratio":        ratio,
                        "Effect":       effect,
                        "Adj Hint":     adj_hint,
                        "Owner":        h["owner"],
                        "Buy Date":     bd,
                        "Current Qty":  h["qty"],
                        "Avg Cost (₹)": h["avg_cost"],
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
        warn  = [r for r in results if r["Status"].startswith("⚠️")]
        ok    = [r for r in results if r["Status"].startswith("✅")]
        unkn  = [r for r in results if r["Status"].startswith("❓")]
        c1, c2, c3 = st.columns(3)
        c1.metric("⚠️ Need Review",    len(warn))
        c2.metric("✅ Likely OK",      len(ok))
        c3.metric("❓ No Buy Date",    len(unkn))

        df = (
            pd.DataFrame(results)
            .sort_values(["Status", "Action Date"], ascending=[True, False])
        )

        def _row_style(row):
            if row["Status"].startswith("⚠️"):
                bg = "background-color:#fff3cd"
            elif row["Status"].startswith("✅"):
                bg = "background-color:#d4edda"
            else:
                bg = "background-color:#f8f9fa"
            return [bg] * len(row)

        st.dataframe(
            df.style.apply(_row_style, axis=1),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Ratio":        st.column_config.NumberColumn("Ratio",        format="%.4g×"),
                "Action Date":  st.column_config.DateColumn( "Action Date",   format="DD-MMM-YYYY"),
                "Buy Date":     st.column_config.DateColumn( "Buy Date",      format="DD-MMM-YYYY"),
                "Current Qty":  st.column_config.NumberColumn("Current Qty",  format="%.2f"),
                "Avg Cost (₹)": st.column_config.NumberColumn("Avg Cost (₹)", format="₹%.2f"),
            },
        )

        st.info(
            "💡 For ⚠️ rows: go to **India Equity → owner tab → 📝 Transactions** and add a "
            "**BONUS** or **SPLIT** entry with the action date and the extra shares received. "
            "The app will auto-recalculate your avg cost."
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
