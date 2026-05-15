"""Portfolio History — daily snapshots with trend charts."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
import pandas as pd
from utils.db  import fetch
from utils.fmt import ind_num

st.set_page_config(page_title="Portfolio History | Wealth Tracker", page_icon="📅", layout="wide")
st.title("📅 Portfolio History")
render_sidebar()

rows = fetch("portfolio_history")
if not rows:
    st.info("No history recorded yet. History is written automatically at 4pm IST on trading days.")
    st.stop()

df = pd.DataFrame(rows)
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_all, tab_vinay, tab_harsh, tab_anusha = st.tabs(["🏠 All", "👤 Vinay", "👤 Harsh", "👤 Anusha"])


def chart_and_table(chart_df, label_inv, label_cv, date_col="date"):
    """Render line chart + summary metrics + data table."""
    latest = chart_df.iloc[-1]
    gl     = float(latest[label_cv]) - float(latest[label_inv])
    ret    = (gl / float(latest[label_inv]) * 100) if float(latest[label_inv]) > 0 else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Invested",      ind_num(latest[label_inv]))
    c2.metric("Current Value", ind_num(latest[label_cv]))
    c3.metric("Gain / Loss",   ind_num(gl), f"{ret:+.2f}%")

    st.subheader("Trend")
    chart_data = chart_df.set_index(date_col)[[label_inv, label_cv]]
    chart_data.columns = ["Invested", "Current Value"]
    st.line_chart(chart_data, use_container_width=True)

    gl_series = chart_df.set_index(date_col)[[label_cv]].copy()
    gl_series["Gain/Loss"] = chart_df[label_cv].values - chart_df[label_inv].values
    st.subheader("Gain / Loss over time")
    st.bar_chart(gl_series[["Gain/Loss"]], use_container_width=True)


def history_table(view_df, money_cols, date_label="Date"):
    """Render the raw history table with Indian number formatting."""
    display = view_df.copy()
    display["date"] = display["date"].dt.strftime("%d-%b-%Y")
    display = display.rename(columns={"date": date_label}).sort_values(date_label, ascending=False)

    fmt = {c: (lambda v: ind_num(v) if v is not None else "—") for c in money_cols if c in display.columns}
    fmt["Return %"] = lambda v: f"{v:+.2f}%" if v is not None else "—"

    st.dataframe(
        display.style
               .format(fmt)
               .map(lambda v: "color:green" if isinstance(v, float) and v >= 0 else
                              "color:red"   if isinstance(v, float) and v <  0 else "",
                    subset=["Gain/Loss", "Return %"] if "Gain/Loss" in display.columns else []),
        use_container_width=True,
        hide_index=True,
    )


# ── All ───────────────────────────────────────────────────────────────────────
with tab_all:
    view = df[["date", "shares_invested", "shares_cv",
               "mf_inv_vinay", "mf_cv_vinay",
               "mf_inv_harsh", "mf_cv_harsh",
               "mf_inv_anusha", "mf_cv_anusha",
               "total_invested", "total_cv", "gain_loss", "return_pct"]].copy()
    view = view.rename(columns={
        "shares_invested": "Shares Invested",
        "shares_cv":       "Shares CV",
        "mf_inv_vinay":   "MF Invested – Vinay",
        "mf_cv_vinay":    "MF CV – Vinay",
        "mf_inv_harsh":   "MF Invested – Harsh",
        "mf_cv_harsh":    "MF CV – Harsh",
        "mf_inv_anusha":  "MF Invested – Anusha",
        "mf_cv_anusha":   "MF CV – Anusha",
        "total_invested": "total_invested",
        "total_cv":       "total_cv",
        "gain_loss":      "Gain/Loss",
        "return_pct":     "Return %",
    })
    chart_and_table(view, "total_invested", "total_cv")
    st.divider()
    money_cols = [c for c in view.columns if c not in ("date", "Return %", "total_invested", "total_cv")]
    money_cols += ["Gain/Loss"]
    final = view.drop(columns=["total_invested", "total_cv"]).copy()
    final["Total Invested"] = df["total_invested"].values
    final["Total CV"]       = df["total_cv"].values
    history_table(final, money_cols + ["Total Invested", "Total CV"])


# ── Vinay (Equity + MF) ───────────────────────────────────────────────────────
with tab_vinay:
    view = df[["date", "shares_invested", "shares_cv", "mf_inv_vinay", "mf_cv_vinay"]].copy()
    view["vinay_invested"] = view["shares_invested"] + view["mf_inv_vinay"]
    view["vinay_cv"]       = view["shares_cv"]       + view["mf_cv_vinay"]
    view["gain_loss"]      = view["vinay_cv"] - view["vinay_invested"]
    chart_and_table(view, "vinay_invested", "vinay_cv")
    st.divider()
    disp = view.rename(columns={
        "shares_invested": "Equity Invested",
        "shares_cv":       "Equity CV",
        "mf_inv_vinay":    "MF Invested",
        "mf_cv_vinay":     "MF CV",
        "vinay_invested":  "Total Invested",
        "vinay_cv":        "Total CV",
        "gain_loss":       "Gain/Loss",
    })
    history_table(disp, ["Equity Invested", "Equity CV", "MF Invested", "MF CV", "Total Invested", "Total CV", "Gain/Loss"])


# ── Harsh MF ──────────────────────────────────────────────────────────────────
with tab_harsh:
    view = df[["date", "mf_inv_harsh", "mf_cv_harsh"]].copy()
    view["gain_loss"] = view["mf_cv_harsh"] - view["mf_inv_harsh"]
    chart_and_table(view, "mf_inv_harsh", "mf_cv_harsh")
    st.divider()
    disp = view.rename(columns={
        "mf_inv_harsh": "MF Invested",
        "mf_cv_harsh":  "MF Current Value",
        "gain_loss":    "Gain/Loss",
    })
    history_table(disp, ["MF Invested", "MF Current Value", "Gain/Loss"])


# ── Anusha MF ─────────────────────────────────────────────────────────────────
with tab_anusha:
    view = df[["date", "mf_inv_anusha", "mf_cv_anusha"]].copy()
    view["gain_loss"] = view["mf_cv_anusha"] - view["mf_inv_anusha"]
    has_data = view["mf_inv_anusha"].sum() > 0
    if has_data:
        chart_and_table(view, "mf_inv_anusha", "mf_cv_anusha")
        st.divider()
        disp = view.rename(columns={
            "mf_inv_anusha": "MF Invested",
            "mf_cv_anusha":  "MF Current Value",
            "gain_loss":     "Gain/Loss",
        })
        history_table(disp, ["MF Invested", "MF Current Value", "Gain/Loss"])
    else:
        st.info("No MF history for Anusha yet — will appear once the daily fetcher runs with her holdings.")
