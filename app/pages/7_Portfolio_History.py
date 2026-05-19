"""Portfolio History — daily snapshots with trend charts."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
import pandas as pd
import plotly.graph_objects as go
from utils.db  import fetch, service_delete
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
tab_vinay, tab_harsh, tab_anusha, tab_all, tab_mom = st.tabs(["👤 Vinay", "👤 Harsh", "👤 Anusha", "🏠 All", "👩 Mom"])


def chart_and_table(chart_df, label_inv, label_cv, date_col="date"):
    """Render line chart + summary metrics + data table."""
    latest = chart_df.iloc[-1]
    gl     = float(latest[label_cv]) - float(latest[label_inv])
    ret    = (gl / float(latest[label_inv]) * 100) if float(latest[label_inv]) > 0 else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Invested",      ind_num(latest[label_inv]))
    c2.metric("Current Value", ind_num(latest[label_cv]))
    c3.metric("Gain / Loss",   ind_num(gl), f"{ret:+.2f}%")

    dates    = chart_df[date_col]
    inv_vals = chart_df[label_inv]
    cv_vals  = chart_df[label_cv]

    # ── Trend line chart ──────────────────────────────────────────────────────
    st.subheader("Trend")
    y_min = min(inv_vals.min(), cv_vals.min()) * 0.995
    y_max = max(inv_vals.max(), cv_vals.max()) * 1.005
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(x=dates, y=inv_vals, mode="lines+markers",
                                   name="Invested", line=dict(color="#636EFA", width=2)))
    fig_trend.add_trace(go.Scatter(x=dates, y=cv_vals,  mode="lines+markers",
                                   name="Current Value", line=dict(color="#00CC96", width=2)))
    fig_trend.update_layout(
        yaxis=dict(range=[y_min, y_max], tickformat=",.0f"),
        xaxis=dict(title="Date"),
        hovermode="x unified", height=380,
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_trend, use_container_width=True)



def history_table(view_df, money_cols, date_label="Date"):
    """Render the raw history table inside a collapsible expander."""
    with st.expander("📋 Raw Data", expanded=False):
        display = view_df.copy()
        display = display.sort_values("date", ascending=False)
        display["date"] = display["date"].dt.strftime("%d-%b-%Y")
        display = display.rename(columns={"date": date_label})

        fmt = {c: (lambda v: ind_num(v) if v is not None else "—") for c in money_cols if c in display.columns}
        fmt["Return %"] = lambda v: f"{v:+.2f}%" if v is not None else "—"

        st.dataframe(
            display.style
                   .format(fmt)
                   .map(lambda v: "color:green" if isinstance(v, float) and v >= 0 else
                                  "color:red"   if isinstance(v, float) and v <  0 else "",
                        subset=[c for c in ["Gain/Loss", "Return %"] if c in display.columns]),
            use_container_width=True,
            hide_index=True,
        )


def delete_widget(source_df, tab_key, table="portfolio_history"):
    """Checkbox + delete button inside a collapsible expander."""
    with st.expander("🗑️ Delete Records", expanded=False):
        chk_rows = [{"☑": False, "Date": d.strftime("%d-%b-%Y"),
                     "Total Invested": ind_num(i), "Total CV": ind_num(c)}
                    for d, i, c in zip(source_df["date"], source_df["total_invested"], source_df["total_cv"])]
        chk_edited = st.data_editor(
            pd.DataFrame(chk_rows),
            column_config={"☑": st.column_config.CheckboxColumn("☑", width="small")},
            disabled=["Date", "Total Invested", "Total CV"],
            hide_index=True, use_container_width=True, key=f"del_chk_{tab_key}",
        )
        if st.button("🗑️ Delete Selected", key=f"del_btn_{tab_key}"):
            sel = chk_edited[chk_edited["☑"]].index.tolist()
            if sel:
                dates_to_del = [source_df["date"].iloc[i].strftime("%Y-%m-%d") for i in sel]
                service_delete(table, "date", dates_to_del)
                st.success(f"✅ {len(sel)} record(s) deleted.")
                st.rerun()
            else:
                st.warning("Select at least one row to delete.")


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
    money_cols = [c for c in view.columns if c not in ("date", "Return %", "total_invested", "total_cv")]
    money_cols += ["Gain/Loss"]
    final = view.drop(columns=["total_invested", "total_cv"]).copy()
    final["Total Invested"] = df["total_invested"].values
    final["Total CV"]       = df["total_cv"].values
    history_table(final, money_cols + ["Total Invested", "Total CV"])
    delete_widget(df, "all")


# ── Vinay (Equity + MF) ───────────────────────────────────────────────────────
with tab_vinay:
    view = df[["date", "shares_invested", "shares_cv", "mf_inv_vinay", "mf_cv_vinay"]].copy()
    view["vinay_invested"] = view["shares_invested"] + view["mf_inv_vinay"]
    view["vinay_cv"]       = view["shares_cv"]       + view["mf_cv_vinay"]
    view["gain_loss"]      = view["vinay_cv"] - view["vinay_invested"]
    chart_and_table(view, "vinay_invested", "vinay_cv")
    disp = view[["date", "shares_invested", "shares_cv", "mf_inv_vinay", "mf_cv_vinay", "vinay_invested", "vinay_cv", "gain_loss"]].rename(columns={
        "shares_invested": "Equity Invested",
        "shares_cv":       "Equity CV",
        "mf_inv_vinay":    "MF Invested",
        "mf_cv_vinay":     "MF CV",
        "vinay_invested":  "Total Invested",
        "vinay_cv":        "Total CV",
        "gain_loss":       "Gain/Loss",
    })
    history_table(disp, ["Equity Invested", "Equity CV", "MF Invested", "MF CV", "Total Invested", "Total CV", "Gain/Loss"])
    delete_widget(df, "vinay")


# ── Harsh MF ──────────────────────────────────────────────────────────────────
with tab_harsh:
    view = df[["date", "mf_inv_harsh", "mf_cv_harsh"]].copy()
    view["gain_loss"] = view["mf_cv_harsh"] - view["mf_inv_harsh"]
    chart_and_table(view, "mf_inv_harsh", "mf_cv_harsh")
    disp = view.rename(columns={
        "mf_inv_harsh": "MF Invested",
        "mf_cv_harsh":  "MF Current Value",
        "gain_loss":    "Gain/Loss",
    })
    history_table(disp, ["MF Invested", "MF Current Value", "Gain/Loss"])
    delete_widget(df, "harsh")


# ── Anusha MF ─────────────────────────────────────────────────────────────────
with tab_anusha:
    view = df[["date", "mf_inv_anusha", "mf_cv_anusha"]].copy()
    view["gain_loss"] = view["mf_cv_anusha"] - view["mf_inv_anusha"]
    has_data = view["mf_inv_anusha"].sum() > 0
    if has_data:
        chart_and_table(view, "mf_inv_anusha", "mf_cv_anusha")
        disp = view.rename(columns={
            "mf_inv_anusha": "MF Invested",
            "mf_cv_anusha":  "MF Current Value",
            "gain_loss":     "Gain/Loss",
        })
        history_table(disp, ["MF Invested", "MF Current Value", "Gain/Loss"])
        delete_widget(df, "anusha")
    else:
        st.info("No MF history for Anusha yet — will appear once the daily fetcher runs with her holdings.")


# ── Mom ───────────────────────────────────────────────────────────────────────
with tab_mom:
    try:
        mom_rows = fetch("portfolio_history_mom")
    except Exception:
        st.warning("⚠️ Table `portfolio_history_mom` not found in Supabase. Please create it — see SQL below.")
        st.code("""create table portfolio_history_mom (
  id             bigserial primary key,
  date           text unique not null,
  eq_invested    numeric default 0,
  eq_cv          numeric default 0,
  mf_invested    numeric default 0,
  mf_cv          numeric default 0,
  total_invested numeric default 0,
  total_cv       numeric default 0,
  gain_loss      numeric default 0,
  return_pct     numeric default 0
);""", language="sql")
        st.stop()
    if not mom_rows:
        st.info("No history for Mom yet — will appear after the daily fetcher runs with her holdings.")
    else:
        mdf = pd.DataFrame(mom_rows)
        mdf["date"] = pd.to_datetime(mdf["date"])
        mdf = mdf.sort_values("date").reset_index(drop=True)

        view = mdf[["date", "eq_invested", "eq_cv", "mf_invested", "mf_cv",
                    "total_invested", "total_cv"]].copy()
        view["gain_loss"] = view["total_cv"] - view["total_invested"]
        chart_and_table(view, "total_invested", "total_cv")
        disp = view.rename(columns={
            "eq_invested":    "Equity Invested",
            "eq_cv":          "Equity CV",
            "mf_invested":    "MF Invested",
            "mf_cv":          "MF CV",
            "total_invested": "Total Invested",
            "total_cv":       "Total CV",
            "gain_loss":      "Gain/Loss",
        })
        history_table(disp, ["Equity Invested", "Equity CV", "MF Invested", "MF CV",
                              "Total Invested", "Total CV", "Gain/Loss"])
        delete_widget(mdf, "mom", table="portfolio_history_mom")
