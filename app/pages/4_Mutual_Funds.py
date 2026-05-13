"""Mutual Funds — Vinay, Harsh, Anusha tabs with Add/Edit/Delete."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from utils.db     import fetch
from utils.config import load, save

st.set_page_config(page_title="Mutual Funds | Wealth Tracker", page_icon="📊", layout="wide")
st.title("📊 Mutual Funds")

navs      = {r["isin"]: r for r in fetch("mf_navs")}
nav_dates = list({r["nav_date"] for r in navs.values() if r.get("nav_date")})
nav_date  = nav_dates[0] if nav_dates else "—"
st.caption(f"NAV Date: {nav_date}")

OWNERS = [
    ("Vinay",  "mutual_funds_vinay.json"),
    ("Harsh",  "mutual_funds_harsh.json"),
    ("Anusha", "mutual_funds_anusha.json"),
]

tabs = st.tabs([o for o, _ in OWNERS])

for tab, (owner, fname) in zip(tabs, OWNERS):
    with tab:
        holdings = load(fname)

        # ── View table ────────────────────────────────────────────────────────
        if holdings:
            total_inv = total_cv = 0.0
            rows = []
            for h in holdings:
                isin  = h.get("isin", "").upper()
                units = float(h.get("units", 0))
                anav  = float(h.get("avg_nav", 0))
                nav_r = navs.get(isin, {})
                nav   = float(nav_r.get("nav", 0)) if nav_r else 0
                amfi  = nav_r.get("amfi_name", "") if nav_r else ""
                inv   = units * anav
                cv    = units * nav if nav > 0 else inv
                gl    = cv - inv
                ret   = (gl / inv * 100) if inv > 0 else 0
                total_inv += inv
                total_cv  += cv
                rows.append({
                    "Folio No": h.get("folio_no", ""), "ISIN No": isin,
                    "Fund Name": h.get("fund_name", ""), "Fund Name (AMFI)": amfi,
                    "Units Held": units, "Avg NAV (₹)": anav,
                    "Invested (₹)": inv, "Current NAV (₹)": nav,
                    "Current Value (₹)": cv, "Gain/Loss (₹)": gl,
                    "Return %": ret, "% of Portfolio": 0.0,
                })

            total_cv_safe = total_cv if total_cv > 0 else 1
            for r in rows:
                r["% of Portfolio"] = r["Current Value (₹)"] / total_cv_safe * 100

            total_gl  = total_cv - total_inv
            total_ret = (total_gl / total_inv * 100) if total_inv > 0 else 0
            rows.append({
                "Folio No": "", "ISIN No": "", "Fund Name": "TOTAL",
                "Fund Name (AMFI)": "", "Units Held": None, "Avg NAV (₹)": None,
                "Invested (₹)": total_inv, "Current NAV (₹)": None,
                "Current Value (₹)": total_cv, "Gain/Loss (₹)": total_gl,
                "Return %": total_ret, "% of Portfolio": 100.0,
            })
            df  = pd.DataFrame(rows)
            fmt = {
                "Units Held":        lambda v: f"{v:,.3f}" if v else "—",
                "Avg NAV (₹)":       lambda v: f"₹ {v:,.4f}" if v else "—",
                "Invested (₹)":      "₹ {:,.2f}",
                "Current NAV (₹)":   lambda v: f"₹ {v:,.4f}" if v else "—",
                "Current Value (₹)": "₹ {:,.2f}",
                "Gain/Loss (₹)":     "₹ {:,.2f}",
                "Return %":          "{:+.2f}%",
                "% of Portfolio":    "{:.2f}%",
            }
            st.dataframe(
                df.style.format(fmt)
                  .map(lambda v: "color:green" if isinstance(v, float) and v >= 0 else
                                      "color:red"   if isinstance(v, float) and v <  0 else "",
                            subset=["Gain/Loss (₹)", "Return %"])
                  .set_properties(**{"font-weight": "bold"}, subset=pd.IndexSlice[df.index[-1], :]),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info(f"No holdings for {owner} yet. Add below.")

        st.divider()

        # ── ADD ───────────────────────────────────────────────────────────────
        with st.expander(f"➕ Add Fund — {owner}"):
            with st.form(f"add_mf_{owner}"):
                c1, c2 = st.columns(2)
                folio    = c1.text_input("Folio No", key=f"folio_{owner}")
                isin_in  = c2.text_input("ISIN No",  key=f"isin_{owner}")
                fund_name = st.text_input("Fund Name (your label)", key=f"fn_{owner}")
                c3, c4 = st.columns(2)
                units    = c3.number_input("Units Held", min_value=0.0, step=0.001,
                                           format="%.3f", key=f"units_{owner}")
                avg_nav  = c4.number_input("Avg NAV (₹)", min_value=0.0, step=0.01,
                                           format="%.4f", key=f"anav_{owner}")
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

        # ── EDIT ──────────────────────────────────────────────────────────────
        if holdings:
            with st.expander(f"✏️ Edit Fund — {owner}"):
                options = [f"{h.get('isin','')} — {h.get('fund_name','')}" for h in holdings]
                sel     = st.selectbox("Select fund", options, key=f"edit_mf_sel_{owner}")
                idx     = options.index(sel)
                h       = holdings[idx]
                with st.form(f"edit_mf_{owner}"):
                    c1, c2 = st.columns(2)
                    folio    = c1.text_input("Folio No",  value=h.get("folio_no",""),  key=f"efolio_{owner}")
                    isin_in  = c2.text_input("ISIN No",   value=h.get("isin",""),      key=f"eisin_{owner}")
                    fund_name = st.text_input("Fund Name", value=h.get("fund_name",""), key=f"efn_{owner}")
                    c3, c4 = st.columns(2)
                    units    = c3.number_input("Units Held", value=float(h.get("units",0)),
                                               min_value=0.0, step=0.001, format="%.3f",
                                               key=f"eunits_{owner}")
                    avg_nav  = c4.number_input("Avg NAV (₹)", value=float(h.get("avg_nav",0)),
                                               min_value=0.0, step=0.01, format="%.4f",
                                               key=f"eanav_{owner}")
                    if st.form_submit_button("Save Changes"):
                        holdings[idx] = {
                            "folio_no": folio.strip(), "isin": isin_in.strip().upper(),
                            "fund_name": fund_name.strip(), "units": units, "avg_nav": avg_nav,
                        }
                        save(fname, holdings)
                        st.success("✅ Changes saved.")
                        st.rerun()

            # ── DELETE ────────────────────────────────────────────────────────
            with st.expander(f"🗑️ Delete Fund — {owner}"):
                options_d = [f"{h.get('isin','')} — {h.get('fund_name','')}" for h in holdings]
                sel_d     = st.selectbox("Select fund to delete", options_d, key=f"del_mf_{owner}")
                idx_d     = options_d.index(sel_d)
                st.warning(f"This will permanently remove **{holdings[idx_d].get('fund_name','')}**.")
                if st.button("Confirm Delete", key=f"del_mf_btn_{owner}"):
                    removed = holdings.pop(idx_d)
                    save(fname, holdings)
                    st.success(f"✅ {removed.get('fund_name','')} removed.")
                    st.rerun()
