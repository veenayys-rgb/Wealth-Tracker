"""Mom Portfolio History — daily snapshots with trend chart."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
import pandas as pd
import plotly.graph_objects as go
from utils.db  import fetch, service_delete
from utils.fmt import ind_num

st.set_page_config(page_title="Mom Portfolio History | Wealth Tracker", page_icon="📅", layout="wide")
st.title("📅 Mom — Portfolio History")
render_sidebar()

rows = fetch("portfolio_history_mom")
if not rows:
    st.info("No history recorded yet. History is written automatically at 4pm IST on trading days.")
    st.stop()

df = pd.DataFrame(rows)
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date").reset_index(drop=True)

# ── Latest metrics ─────────────────────────────────────────────────────────────
latest = df.iloc[-1]
gl  = float(latest["total_cv"]) - float(latest["total_invested"])
ret = (gl / float(latest["total_invested"]) * 100) if float(latest["total_invested"]) > 0 else 0.0

c1, c2, c3 = st.columns(3)
c1.metric("Invested",      ind_num(latest["total_invested"]))
c2.metric("Current Value", ind_num(latest["total_cv"]))
c3.metric("Gain / Loss",   ind_num(gl), f"{ret:+.2f}%")

# ── Trend chart ────────────────────────────────────────────────────────────────
st.subheader("Trend")
inv_vals = df["total_invested"]
cv_vals  = df["total_cv"]
y_min = min(inv_vals.min(), cv_vals.min()) * 0.995
y_max = max(inv_vals.max(), cv_vals.max()) * 1.005

fig = go.Figure()
fig.add_trace(go.Scatter(x=df["date"], y=inv_vals, mode="lines+markers",
                          name="Invested", line=dict(color="#636EFA", width=2)))
fig.add_trace(go.Scatter(x=df["date"], y=cv_vals,  mode="lines+markers",
                          name="Current Value", line=dict(color="#00CC96", width=2)))
fig.update_layout(
    yaxis=dict(range=[y_min, y_max], tickformat=",.0f"),
    xaxis=dict(title="Date"),
    hovermode="x unified", height=380,
    margin=dict(l=0, r=0, t=10, b=0),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
)
st.plotly_chart(fig, use_container_width=True)

# ── Raw data ───────────────────────────────────────────────────────────────────
with st.expander("📋 Raw Data", expanded=False):
    disp = df.copy().sort_values("date", ascending=False)
    disp["date"] = disp["date"].dt.strftime("%d-%b-%Y")
    disp = disp.rename(columns={
        "date":            "Date",
        "eq_invested":     "Equity Invested",
        "eq_cv":           "Equity CV",
        "mf_invested":     "MF Invested",
        "mf_cv":           "MF CV",
        "total_invested":  "Total Invested",
        "total_cv":        "Total CV",
        "gain_loss":       "Gain/Loss",
        "return_pct":      "Return %",
    })
    money_cols = ["Equity Invested", "Equity CV", "MF Invested", "MF CV",
                  "Total Invested", "Total CV", "Gain/Loss"]
    fmt = {c: (lambda v: ind_num(v) if v is not None else "—") for c in money_cols if c in disp.columns}
    fmt["Return %"] = lambda v: f"{v:+.2f}%" if v is not None else "—"
    st.dataframe(
        disp.style.format(fmt)
                  .map(lambda v: "color:green" if isinstance(v, float) and v >= 0 else
                                 "color:red"   if isinstance(v, float) and v <  0 else "",
                       subset=[c for c in ["Gain/Loss", "Return %"] if c in disp.columns]),
        use_container_width=True, hide_index=True,
    )

# ── Delete records ─────────────────────────────────────────────────────────────
with st.expander("🗑️ Delete Records", expanded=False):
    chk_rows = [{"☑": False, "Date": d.strftime("%d-%b-%Y"),
                 "Total Invested": ind_num(i), "Total CV": ind_num(c)}
                for d, i, c in zip(df["date"], df["total_invested"], df["total_cv"])]
    chk_edited = st.data_editor(
        pd.DataFrame(chk_rows),
        column_config={"☑": st.column_config.CheckboxColumn("☑", width="small")},
        disabled=["Date", "Total Invested", "Total CV"],
        hide_index=True, use_container_width=True, key="del_chk_mom",
    )
    if st.button("🗑️ Delete Selected", key="del_btn_mom"):
        sel = chk_edited[chk_edited["☑"]].index.tolist()
        if sel:
            dates_to_del = [df["date"].iloc[i].strftime("%Y-%m-%d") for i in sel]
            service_delete("portfolio_history_mom", "date", dates_to_del)
            st.success(f"✅ {len(sel)} record(s) deleted.")
            st.rerun()
        else:
            st.warning("Select at least one row to delete.")
