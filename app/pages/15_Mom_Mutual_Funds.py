"""Mom Mutual Funds — holdings. Display + Quick Edit + Add/Edit/Delete."""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
import pandas as pd
from utils.db     import fetch, service_upsert
from utils.config import load, save
from utils.fmt    import ind_num, total_metrics

st.set_page_config(page_title="Mom Mutual Funds | Wealth Tracker", page_icon="📊", layout="wide")
st.title("📊 Mom — Mutual Funds")
render_sidebar()

navs      = {r["isin"]: r for r in fetch("mf_navs")}
nav_dates = list({r["nav_date"] for r in navs.values() if r.get("nav_date")})
nav_date  = nav_dates[0] if nav_dates else "—"
st.caption(f"NAV Date: {nav_date}")

FNAME    = "mom_mutual_funds.json"
holdings = load(FNAME)

# ── Display table ──────────────────────────────────────────────────────────────
if holdings:
    total_inv = total_cv = 0.0
    rows = []
    for h in holdings:
        isin  = h.get("isin", "").upper()
        units = float(h.get("units", 0))
        anav  = float(h.get("avg_nav", 0))
        nav_r = navs.get(isin, {})
        nav   = float(nav_r.get("nav", 0)) if nav_r else 0.0
        amfi  = nav_r.get("amfi_name", "") if nav_r else ""
        inv   = units * anav
        cv    = units * nav if nav > 0 else inv
        gl    = cv - inv
        ret   = (gl / inv * 100) if inv > 0 else 0.0
        total_inv += inv
        total_cv  += cv
        rows.append({
            "Fund Name (AMFI)":  amfi or h.get("fund_name") or "—",
            "Units Held":        units,
            "Avg NAV (₹)":       anav,
            "Invested (₹)":      inv,
            "Current NAV (₹)":   nav if nav > 0 else None,
            "Current Value (₹)": cv,
            "Gain/Loss (₹)":     gl,
            "Return %":          ret,
            "% of Portfolio":    0.0,
            "Folio No":          h.get("folio_no") or "—",
            "ISIN No":           isin or "—",
            "Fund Name":         h.get("fund_name") or "—",
        })

    total_cv_safe = total_cv if total_cv > 0 else 1.0
    for r in rows:
        r["% of Portfolio"] = r["Current Value (₹)"] / total_cv_safe * 100

    df  = pd.DataFrame(rows)
    fmt = {
        "Units Held":        lambda v: f"{v:,.3f}" if v is not None else "—",
        "Avg NAV (₹)":       lambda v: ind_num(v, decimals=4) if v is not None else "—",
        "Invested (₹)":      lambda v: ind_num(v),
        "Current NAV (₹)":   lambda v: ind_num(v, decimals=4) if v is not None else "—",
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
        column_config={"Fund Name (AMFI)": st.column_config.TextColumn(width="large")},
    )
    total_metrics(total_inv, total_cv)
else:
    st.info("No mutual fund holdings for Mom yet. Add below.")

st.divider()

# ── Quick Edit ─────────────────────────────────────────────────────────────────
if holdings:
    with st.expander("✏️ Quick Edit"):
        qe_rows = []
        for h in holdings:
            isin    = h.get("isin", "").upper()
            amfi    = navs.get(isin, {}).get("amfi_name") or h.get("fund_name") or isin or "—"
            nav_val = float(navs.get(isin, {}).get("nav", 0) or 0)
            qe_rows.append({
                "☑":               False,
                "Fund Name (AMFI)": amfi,
                "Units Held":       float(h.get("units", 0)),
                "Avg NAV (₹)":      float(h.get("avg_nav", 0)),
                "Current NAV (₹)":  nav_val,
            })
        edited = st.data_editor(
            pd.DataFrame(qe_rows),
            column_config={
                "☑":               st.column_config.CheckboxColumn("☑", width="small"),
                "Fund Name (AMFI)": st.column_config.TextColumn(disabled=True, width="large"),
                "Units Held":       st.column_config.NumberColumn(format="%.3f", min_value=0.0),
                "Avg NAV (₹)":      st.column_config.NumberColumn(format="%.4f", min_value=0.0),
                "Current NAV (₹)":  st.column_config.NumberColumn(format="%.4f", min_value=0.0),
            },
            hide_index=True, use_container_width=True, key="qe_mom_mf",
        )
        bc1, bc2 = st.columns(2)
        if bc1.button("💾 Save Changes", key="qsave_mom_mf"):
            nav_rows = []
            for i in range(len(holdings)):
                holdings[i]["units"]   = float(edited.iloc[i]["Units Held"])
                holdings[i]["avg_nav"] = float(edited.iloc[i]["Avg NAV (₹)"])
                new_nav = float(edited.iloc[i]["Current NAV (₹)"] or 0)
                if new_nav > 0:
                    nav_rows.append({"isin": holdings[i]["isin"],
                                     "nav": round(new_nav, 4),
                                     "nav_date": datetime.date.today().isoformat(),
                                     "fetched_at": datetime.datetime.utcnow().isoformat()})
            save(FNAME, holdings)
            if nav_rows:
                deduped = list({r["isin"]: r for r in nav_rows}.values())
                try:
                    service_upsert("mf_navs", deduped, conflict_col="isin")
                except Exception as e:
                    st.warning(f"Holdings saved but NAV update failed: {e}")
            st.success("✅ Changes saved.")
            st.rerun()
        if bc2.button("🗑️ Delete Selected", key="del_mom_mf"):
            sel = edited[edited["☑"]].index.tolist()
            if sel:
                for j in sorted(sel, reverse=True):
                    holdings.pop(j)
                save(FNAME, holdings)
                st.success(f"✅ {len(sel)} fund(s) removed.")
                st.rerun()
            else:
                st.warning("Tick at least one row to delete.")

# ── Add ────────────────────────────────────────────────────────────────────────
with st.expander("➕ Add Fund"):
    with st.form("add_mom_mf"):
        c1, c2 = st.columns(2)
        folio     = c1.text_input("Folio No")
        isin_in   = c2.text_input("ISIN No")
        fund_name = st.text_input("Fund Name (your label)")
        c3, c4 = st.columns(2)
        units   = c3.number_input("Units Held",  min_value=0.0, step=0.001, format="%.3f")
        avg_nav = c4.number_input("Avg NAV (₹)", min_value=0.0, step=0.01,  format="%.4f")
        if st.form_submit_button("Add Fund"):
            if not isin_in.strip():
                st.error("ISIN is required.")
            else:
                holdings.append({
                    "folio_no":  folio.strip(),
                    "isin":      isin_in.strip().upper(),
                    "fund_name": fund_name.strip(),
                    "units":     units,
                    "avg_nav":   avg_nav,
                })
                save(FNAME, holdings)
                st.success("✅ Fund added.")
                st.rerun()

# ── Edit details ───────────────────────────────────────────────────────────────
if holdings:
    with st.expander("✏️ Edit Fund Details"):
        opts = [f"{h.get('isin','—')} — {h.get('fund_name','—')}" for h in holdings]
        sel  = st.selectbox("Select fund", opts, key="edit_mom_mf_sel")
        idx  = opts.index(sel)
        h    = holdings[idx]
        with st.form("edit_mom_mf"):
            c1, c2 = st.columns(2)
            folio     = c1.text_input("Folio No",  value=h.get("folio_no",""))
            isin_in   = c2.text_input("ISIN No",   value=h.get("isin",""))
            fund_name = st.text_input("Fund Name", value=h.get("fund_name",""))
            if st.form_submit_button("Save Details"):
                holdings[idx].update({
                    "folio_no":  folio.strip(),
                    "isin":      isin_in.strip().upper(),
                    "fund_name": fund_name.strip(),
                })
                save(FNAME, holdings)
                st.success("✅ Details saved.")
                st.rerun()
