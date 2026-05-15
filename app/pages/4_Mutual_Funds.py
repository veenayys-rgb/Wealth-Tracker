"""Mutual Funds — Vinay, Harsh, Anusha tabs. Display + Quick Edit + Add/Edit/Delete."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
import pandas as pd
import datetime
from utils.db     import fetch, service_upsert
from utils.config import load, save
from utils.fmt    import ind_num, total_metrics

st.set_page_config(page_title="Mutual Funds | Wealth Tracker", page_icon="📊", layout="wide")
st.title("📊 Mutual Funds")
render_sidebar()

navs      = {r["isin"]: r for r in fetch("mf_navs")}
nav_dates = list({r["nav_date"] for r in navs.values() if r.get("nav_date")})
nav_date  = nav_dates[0] if nav_dates else "—"
st.caption(f"NAV Date: {nav_date}")

OWNERS = [
    ("Vinay",  "mutual_funds_vinay.json"),
    ("Harsh",  "mutual_funds_harsh.json"),
    ("Anusha", "mutual_funds_anusha.json"),
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
                # column order: AMFI name first, user cols at end
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

            total_gl  = total_cv - total_inv
            total_ret = (total_gl / total_inv * 100) if total_inv > 0 else 0.0

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
                column_config={
                    "Fund Name (AMFI)": st.column_config.TextColumn(width="large"),
                },
            )
            total_metrics(total_inv, total_cv)

            st.divider()
            chk_rows = [{"☑": False, "ISIN": h.get("isin",""), "Fund Name": h.get("fund_name","") or (navs.get(h.get("isin","").upper(), {}).get("amfi_name") or "—")} for h in holdings]
            chk_edited = st.data_editor(
                pd.DataFrame(chk_rows),
                column_config={"☑": st.column_config.CheckboxColumn("☑", width="small")},
                disabled=["ISIN", "Fund Name"],
                hide_index=True, use_container_width=True, key=f"del_chk_mf_{owner}",
            )
            if st.button("🗑️ Delete Selected", key=f"del_mf_btn_{owner}"):
                sel = chk_edited[chk_edited["☑"]].index.tolist()
                if sel:
                    for j in sorted(sel, reverse=True):
                        holdings.pop(j)
                    save(fname, holdings)
                    st.success(f"✅ {len(sel)} fund(s) removed.")
                    st.rerun()
                else:
                    st.warning("Select at least one row to delete.")

        else:
            st.info(f"No holdings for {owner} yet. Add below.")

        st.divider()

        # ── Quick Edit ────────────────────────────────────────────────────────
        if holdings:
            with st.expander("✏️ Quick Edit"):
                qe_rows = []
                for h in holdings:
                    isin = h.get("isin", "").upper()
                    amfi = (navs.get(isin, {}).get("amfi_name") or h.get("fund_name") or isin or "—")
                    nav_val = float(navs.get(isin, {}).get("nav", 0) or 0)
                    qe_rows.append({
                        "Fund Name (AMFI)": amfi,
                        "Units Held":       float(h.get("units", 0)),
                        "Avg NAV (₹)":      float(h.get("avg_nav", 0)),
                        "Current NAV (₹)":  nav_val,
                    })
                qe_df  = pd.DataFrame(qe_rows)
                edited = st.data_editor(
                    qe_df,
                    column_config={
                        "Fund Name (AMFI)": st.column_config.TextColumn(disabled=True, width="large"),
                        "Units Held":       st.column_config.NumberColumn(format="%.3f", min_value=0.0),
                        "Avg NAV (₹)":      st.column_config.NumberColumn(format="%.4f", min_value=0.0),
                        "Current NAV (₹)":  st.column_config.NumberColumn(format="%.4f", min_value=0.0),
                    },
                    hide_index=True,
                    use_container_width=True,
                    key=f"qe_{owner}",
                )
                if st.button("💾 Save Changes", key=f"qsave_{owner}"):
                    nav_rows = []
                    for i in range(len(holdings)):
                        holdings[i]["units"]     = float(edited.iloc[i]["Units Held"])
                        holdings[i]["avg_nav"]   = float(edited.iloc[i]["Avg NAV (₹)"])
                        new_nav = float(edited.iloc[i]["Current NAV (₹)"] or 0)
                        if new_nav > 0:
                            nav_rows.append({"isin": holdings[i]["isin"],
                                             "nav": round(new_nav, 4),
                                             "nav_date": datetime.date.today().isoformat(),
                                             "fetched_at": datetime.datetime.utcnow().isoformat()})
                    save(fname, holdings)
                    if nav_rows:
                        deduped = list({r["isin"]: r for r in nav_rows}.values())
                        try:
                            service_upsert("mf_navs", deduped, conflict_col="isin")
                        except Exception as e:
                            st.warning(f"Holdings saved but NAV update failed: {e}")
                    st.success("✅ Changes saved.")
                    st.rerun()

        # ── Add ───────────────────────────────────────────────────────────────
        with st.expander(f"➕ Add Fund — {owner}"):
            with st.form(f"add_mf_{owner}"):
                c1, c2 = st.columns(2)
                folio     = c1.text_input("Folio No",  key=f"folio_{owner}")
                isin_in   = c2.text_input("ISIN No",   key=f"isin_{owner}")
                fund_name = st.text_input("Fund Name (your label)", key=f"fn_{owner}")
                c3, c4 = st.columns(2)
                units   = c3.number_input("Units Held",  min_value=0.0, step=0.001, format="%.3f", key=f"units_{owner}")
                avg_nav = c4.number_input("Avg NAV (₹)", min_value=0.0, step=0.01,  format="%.4f", key=f"anav_{owner}")
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
                        save(fname, holdings)
                        st.success(f"✅ Fund added for {owner}.")
                        st.rerun()

        # ── Edit details (Folio / ISIN / Fund Name) ───────────────────────────
        if holdings:
            with st.expander(f"✏️ Edit Fund Details — {owner}"):
                opts = [f"{h.get('isin','—')} — {h.get('fund_name','—')}" for h in holdings]
                sel  = st.selectbox("Select fund", opts, key=f"edit_mf_sel_{owner}")
                idx  = opts.index(sel)
                h    = holdings[idx]
                with st.form(f"edit_mf_{owner}"):
                    c1, c2 = st.columns(2)
                    folio     = c1.text_input("Folio No",  value=h.get("folio_no",""),  key=f"efolio_{owner}")
                    isin_in   = c2.text_input("ISIN No",   value=h.get("isin",""),      key=f"eisin_{owner}")
                    fund_name = st.text_input("Fund Name", value=h.get("fund_name",""), key=f"efn_{owner}")
                    if st.form_submit_button("Save Details"):
                        holdings[idx].update({
                            "folio_no":  folio.strip(),
                            "isin":      isin_in.strip().upper(),
                            "fund_name": fund_name.strip(),
                        })
                        save(fname, holdings)
                        st.success("✅ Details saved.")
                        st.rerun()


# ── All ───────────────────────────────────────────────────────────────────────
with tab_all:
    all_rows = []
    grand_inv = grand_cv = 0.0
    for owner, fname in OWNERS:
        for h in load(fname):
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
            grand_inv += inv
            grand_cv  += cv
            all_rows.append({
                "Owner":             owner,
                "Fund Name (AMFI)":  amfi or h.get("fund_name") or "—",
                "Units Held":        units,
                "Avg NAV (₹)":       anav,
                "Invested (₹)":      inv,
                "Current NAV (₹)":   nav if nav > 0 else None,
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
        total_metrics(grand_inv, grand_cv)
    else:
        st.info("No mutual fund holdings yet.")

