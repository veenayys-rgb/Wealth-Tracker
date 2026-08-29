"""Mutual Funds — Vinay, Harsh, Anusha, Mom tabs. Display + Quick Edit + Add/Edit/Delete."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar, apply_prev_nav
import pandas as pd
import datetime, urllib.request, ssl
from utils.db     import fetch, service_upsert
from utils.config import load, save
from utils.fmt    import ind_num, total_metrics, fmt_date, parse_date

AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"


def refresh_navs_from_amfi(isins: list[str]) -> tuple[int, int]:
    """Fetch AMFI NAVAll.txt and upsert NAVs for the given ISINs.
    Returns (updated_count, not_found_count)."""
    if not isins:
        return 0, 0
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    resp  = urllib.request.urlopen(AMFI_URL, timeout=30, context=ctx)
    lines = resp.read().decode("utf-8", errors="ignore").splitlines()

    # AMFI NAVAll.txt format (8 columns as of Aug 2025):
    #   Code; ISIN Growth; ISIN Div-Reinv; Scheme Name; Plan; Option; NAV; Date
    amfi_index: dict[str, dict] = {}
    for line in lines:
        parts = line.strip().split(";")
        if len(parts) < 8:
            continue
        try:
            nav  = float(parts[6].strip())
            name = parts[3].strip()
            date = parts[7].strip()
            for isin in [parts[1].strip().upper(), parts[2].strip().upper()]:
                if isin and isin != "-":
                    amfi_index[isin] = {"nav": nav, "name": name, "date": date}
        except (ValueError, IndexError):
            pass

    def _amfi_date_to_iso(s: str) -> str:
        try:
            return datetime.datetime.strptime(s.strip(), "%d-%b-%Y").strftime("%Y-%m-%d")
        except ValueError:
            return s.strip()

    rows, missing = [], []
    for isin in isins:
        if isin in amfi_index:
            d = amfi_index[isin]
            rows.append({
                "isin":       isin,
                "nav":        d["nav"],
                "nav_date":   _amfi_date_to_iso(d["date"]),
                "amfi_name":  d["name"],
                "fetched_at": datetime.datetime.utcnow().isoformat(),
            })
        else:
            missing.append(isin)

    if rows:
        rows = apply_prev_nav(rows)
        service_upsert("mf_navs", rows, conflict_col="isin")
    return len(rows), len(missing)


st.set_page_config(page_title="Mutual Funds | Wealth Tracker", page_icon="📊", layout="wide")
st.title("📊 Mutual Funds")
render_sidebar()

OWNERS = [
    ("Vinay",  "mutual_funds_vinay.json"),
    ("Harsh",  "mutual_funds_harsh.json"),
    ("Anusha", "mutual_funds_anusha.json"),
    ("Mom",    "mom_mutual_funds.json"),
]

navs      = {r["isin"]: r for r in fetch("mf_navs")}
prev_navs = {r["isin"]: float(r["prev_nav"]) for r in navs.values() if r.get("prev_nav")}

# Pick the most recent nav_date across all funds
_dated   = [(parse_date(r["nav_date"]), r["nav_date"]) for r in navs.values() if r.get("nav_date")]
_dated   = [(d, s) for d, s in _dated if d is not None]
nav_date = fmt_date(max(_dated, key=lambda x: x[0])[1]) if _dated else "—"

hdr_col, btn_col = st.columns([4, 1])
hdr_col.caption(f"NAV Date: {nav_date}")
if btn_col.button("🔄 Refresh NAVs", help="Pull latest NAVs from AMFI for all holdings"):
    all_isins = list({
        h.get("isin", "").strip().upper()
        for _, fname in OWNERS
        for h in load(fname)
        if h.get("isin", "").strip()
    })
    with st.spinner(f"Fetching {len(all_isins)} NAVs from AMFI…"):
        try:
            ok, miss = refresh_navs_from_amfi(all_isins)
            if miss:
                st.warning(f"Updated {ok} NAVs — {miss} ISIN(s) not found in AMFI.")
            else:
                st.success(f"✅ {ok} NAVs updated from AMFI.")
            st.rerun()
        except Exception as e:
            st.error(f"AMFI fetch failed: {e}")

all_tabs   = st.tabs([o for o, _ in OWNERS] + ["🏠 All"])
owner_tabs = all_tabs[:len(OWNERS)]
tab_all    = all_tabs[-1]


def _day_view_mf(dv_holdings, show_owner: str | None = None):
    """Render MF Day View table."""
    if not dv_holdings:
        st.info("No holdings found.")
        return
    rows = []
    for h in dv_holdings:
        isin      = h.get("isin", "").upper()
        units     = float(h.get("units", 0))
        avg_nav   = float(h.get("avg_nav", 0))
        nav_r     = navs.get(isin, {})
        nav       = float(nav_r.get("nav", 0)) if nav_r else 0.0
        prev_nav  = prev_navs.get(isin, 0)
        fund_name = (nav_r.get("amfi_name") or h.get("fund_name") or isin or "—") if nav_r \
                    else (h.get("fund_name") or isin or "—")
        invested  = units * avg_nav
        value     = units * nav if nav > 0 else invested
        gl        = value - invested
        day_gl    = (nav - prev_nav) * units if nav > 0 and prev_nav > 0 else None
        day_pct   = ((nav - prev_nav) / prev_nav * 100) if nav > 0 and prev_nav > 0 else None
        row = {
            "Fund":     fund_name,
            "Units":    units,
            "Invested": invested,
            "NAV":      nav      if nav      > 0 else None,
            "Value":    value,
            "G/L":      gl,
            "Prev NAV": prev_nav if prev_nav > 0 else None,
            "Day G/L":  day_gl,
            "Day %":    day_pct,
        }
        if show_owner:
            row = {"Owner": show_owner, **row}
        rows.append(row)

    df_dv = pd.DataFrame(rows).sort_values("Day %", ascending=False, na_position="last")
    col_cfg = {
        "Fund":     st.column_config.TextColumn("Fund"),
        "Units":    st.column_config.NumberColumn("Units",    format="%.3f"),
        "Invested": st.column_config.NumberColumn("Invested", format="₹%.0f"),
        "NAV":      st.column_config.NumberColumn("NAV",      format="₹%.4f"),
        "Value":    st.column_config.NumberColumn("Value",    format="₹%.0f"),
        "G/L":      st.column_config.NumberColumn("G/L",      format="₹%.0f"),
        "Prev NAV": st.column_config.NumberColumn("Prev NAV", format="₹%.4f"),
        "Day G/L":  st.column_config.NumberColumn("Day G/L",  format="₹%.0f"),
        "Day %":    st.column_config.NumberColumn("Day %",    format="%.2f%%"),
    }
    if show_owner:
        col_cfg = {"Owner": st.column_config.TextColumn("Owner"), **col_cfg}

    st.dataframe(
        df_dv.style.map(lambda v: "color:green" if isinstance(v, float) and v >= 0
                              else "color:red"   if isinstance(v, float) and v <  0
                              else "", subset=["G/L", "Day G/L", "Day %"]),
        use_container_width=True, hide_index=True, column_config=col_cfg,
    )
    total_inv = sum(r["Invested"] for r in rows)
    total_val = sum(r["Value"]    for r in rows)
    total_gl  = total_val - total_inv
    total_dgl = sum(r["Day G/L"] for r in rows if r["Day G/L"] is not None)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Invested", ind_num(total_inv))
    c2.metric("Value",    ind_num(total_val))
    c3.metric("G/L",      ind_num(total_gl))
    c4.metric("Day G/L",  ind_num(total_dgl),
              delta=f"{(total_dgl/total_val*100):+.2f}%" if total_val > 0 else None)


# ── Per-owner tabs ─────────────────────────────────────────────────────────────
for tab, (owner, fname) in zip(owner_tabs, OWNERS):
    with tab:
        holdings = load(fname)
        sub_h, sub_d = st.tabs(["📋 Holdings", "📊 Day View"])

        # ── Holdings ──────────────────────────────────────────────────────────
        with sub_h:
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
                    use_container_width=True, hide_index=True,
                    column_config={"Fund Name (AMFI)": st.column_config.TextColumn(width="large")},
                )
                total_metrics(total_inv, total_cv)
            else:
                st.info(f"No holdings for {owner} yet. Add below.")

            st.divider()

            # ── Quick Edit ────────────────────────────────────────────────
            if holdings:
                with st.expander("✏️ Quick Edit"):
                    qe_rows = []
                    for h in holdings:
                        isin    = h.get("isin", "").upper()
                        amfi    = (navs.get(isin, {}).get("amfi_name") or h.get("fund_name") or isin or "—")
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
                        hide_index=True, use_container_width=True, key=f"qe_{owner}",
                    )
                    bc1, bc2 = st.columns(2)
                    if bc1.button("💾 Save Changes", key=f"qsave_{owner}"):
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
                        save(fname, holdings)
                        if nav_rows:
                            deduped = list({r["isin"]: r for r in nav_rows}.values())
                            try:
                                service_upsert("mf_navs", deduped, conflict_col="isin")
                            except Exception as e:
                                st.warning(f"Holdings saved but NAV update failed: {e}")
                        st.success("✅ Changes saved.")
                        st.rerun()
                    if bc2.button("🗑️ Delete Selected", key=f"del_mf_btn_{owner}"):
                        sel = edited[edited["☑"]].index.tolist()
                        if sel:
                            for j in sorted(sel, reverse=True):
                                holdings.pop(j)
                            save(fname, holdings)
                            st.success(f"✅ {len(sel)} fund(s) removed.")
                            st.rerun()
                        else:
                            st.warning("Tick at least one row to delete.")

            # ── Add ───────────────────────────────────────────────────────
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

            # ── Edit details ──────────────────────────────────────────────
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

        # ── Day View ──────────────────────────────────────────────────────────
        with sub_d:
            _day_view_mf(holdings)


# ── All ───────────────────────────────────────────────────────────────────────
with tab_all:
    sub_all_h, sub_all_d = st.tabs(["📋 Holdings", "📊 Day View"])

    with sub_all_h:
        all_rows  = []
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
                use_container_width=True, hide_index=True,
                column_config={"Fund Name (AMFI)": st.column_config.TextColumn(width="large")},
            )
            total_metrics(grand_inv, grand_cv)
        else:
            st.info("No mutual fund holdings yet.")

    with sub_all_d:
        all_dv = []
        for owner, fname in OWNERS:
            for h in load(fname):
                all_dv.append({**h, "_owner": owner})
        if not all_dv:
            st.info("No mutual fund holdings yet.")
        else:
            dv_rows = []
            for h in all_dv:
                isin      = h.get("isin", "").upper()
                units     = float(h.get("units", 0))
                avg_nav   = float(h.get("avg_nav", 0))
                nav_r     = navs.get(isin, {})
                nav       = float(nav_r.get("nav", 0)) if nav_r else 0.0
                prev_nav  = prev_navs.get(isin, 0)
                fund_name = (nav_r.get("amfi_name") or h.get("fund_name") or isin or "—") if nav_r \
                            else (h.get("fund_name") or isin or "—")
                invested  = units * avg_nav
                value     = units * nav if nav > 0 else invested
                gl        = value - invested
                day_gl    = (nav - prev_nav) * units if nav > 0 and prev_nav > 0 else None
                day_pct   = ((nav - prev_nav) / prev_nav * 100) if nav > 0 and prev_nav > 0 else None
                dv_rows.append({
                    "Owner":    h["_owner"],
                    "Fund":     fund_name,
                    "Units":    units,
                    "Invested": invested,
                    "NAV":      nav      if nav      > 0 else None,
                    "Value":    value,
                    "G/L":      gl,
                    "Prev NAV": prev_nav if prev_nav > 0 else None,
                    "Day G/L":  day_gl,
                    "Day %":    day_pct,
                })
            df_dv  = pd.DataFrame(dv_rows).sort_values("Day %", ascending=False, na_position="last")
            st.dataframe(
                df_dv.style.map(lambda v: "color:green" if isinstance(v, float) and v >= 0
                                      else "color:red"   if isinstance(v, float) and v <  0
                                      else "", subset=["G/L", "Day G/L", "Day %"]),
                use_container_width=True, hide_index=True,
                column_config={
                    "Owner":    st.column_config.TextColumn("Owner"),
                    "Fund":     st.column_config.TextColumn("Fund"),
                    "Units":    st.column_config.NumberColumn("Units",    format="%.3f"),
                    "Invested": st.column_config.NumberColumn("Invested", format="₹%.0f"),
                    "NAV":      st.column_config.NumberColumn("NAV",      format="₹%.4f"),
                    "Value":    st.column_config.NumberColumn("Value",    format="₹%.0f"),
                    "G/L":      st.column_config.NumberColumn("G/L",      format="₹%.0f"),
                    "Prev NAV": st.column_config.NumberColumn("Prev NAV", format="₹%.4f"),
                    "Day G/L":  st.column_config.NumberColumn("Day G/L",  format="₹%.0f"),
                    "Day %":    st.column_config.NumberColumn("Day %",    format="%.2f%%"),
                },
            )
            total_inv = sum(r["Invested"] for r in dv_rows)
            total_val = sum(r["Value"]    for r in dv_rows)
            total_gl  = total_val - total_inv
            total_dgl = sum(r["Day G/L"] for r in dv_rows if r["Day G/L"] is not None)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Invested", ind_num(total_inv))
            c2.metric("Value",    ind_num(total_val))
            c3.metric("G/L",      ind_num(total_gl))
            c4.metric("Day G/L",  ind_num(total_dgl),
                      delta=f"{(total_dgl/total_val*100):+.2f}%" if total_val > 0 else None)
