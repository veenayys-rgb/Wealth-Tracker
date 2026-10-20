"""Fixed Deposits — India & UAE. Owner tabs + checkbox delete."""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
import pandas as pd
from utils.db     import get_forex, fetch_nominees_map, save_nominee
from utils.config import load, save
from utils.fmt    import fmt_date, parse_date

st.set_page_config(page_title="Fixed Deposits | Wealth Tracker", page_icon="🏛️", layout="wide")
st.title("🏛️ Fixed Deposits")
render_sidebar()

forex = get_forex()
aed   = forex.get("AED_INR", 0)
usd   = forex.get("USD_INR", 0)
st.caption(f"AED/INR: {aed:.4f}  |  USD/INR: {usd:.4f}")

fds      = load("fixed_deposits.json")
nom_map  = fetch_nominees_map("fd")

OWNERS       = ["Vinay", "Harsh", "Anusha", "Mom"]
CURRENCIES   = ["INR", "AED", "USD", "GBP", "EUR", "Other"]
OWNER_LABELS = ["👤 Vinay", "👤 Harsh", "👤 Anusha", "👩 Mom", "🏠 All"]
OWNER_FILTERS = OWNERS + [None]

_NOMINEES = ["Anusha", "Vinay", "Harsh", "Mom", "Other"]
_RELS     = ["Spouse", "Son", "Daughter", "Father", "Mother", "Brother", "Sister", "Other"]


def _blank(v):
    return v if v else "—"


def _inr_rate(curr):
    if curr == "AED": return aed
    if curr == "USD": return usd
    return 1.0


def _nom_section(form_key, existing_nom=None):
    st.divider()
    st.markdown("**🎯 Nominee**")
    _nom_idx = (_NOMINEES.index(existing_nom["nominee_name"]) + 1
                if existing_nom and existing_nom.get("nominee_name") in _NOMINEES else 0)
    _rel_idx = (_RELS.index(existing_nom["relationship"]) + 1
                if existing_nom and existing_nom.get("relationship") in _RELS else 0)
    _pct_val = float(existing_nom.get("share_pct", 100) or 100) if existing_nom else 100.0
    _reg_val = bool(existing_nom.get("nomination_registered", False)) if existing_nom else False
    _notes_v = (existing_nom.get("notes") or "") if existing_nom else ""
    nc1, nc2, nc3 = st.columns(3)
    nom_name = nc1.selectbox("Nominee Name", [""] + _NOMINEES, index=_nom_idx, key=f"{form_key}_nn")
    nom_pct  = nc2.number_input("Share %", 0.0, 100.0, _pct_val, step=1.0, key=f"{form_key}_pct")
    nom_rel  = nc3.selectbox("Relationship", [""] + _RELS, index=_rel_idx, key=f"{form_key}_rel")
    nc4, nc5 = st.columns(2)
    nom_reg   = nc4.checkbox("Nomination Registered", value=_reg_val, key=f"{form_key}_reg")
    nom_notes = nc5.text_input("Nominee Notes", value=_notes_v, key=f"{form_key}_notes", placeholder="(optional)")
    return nom_name, nom_pct, nom_rel, nom_reg, nom_notes


owner_tabs = st.tabs(OWNER_LABELS)

for oi, (owner_tab, owner_filter) in enumerate(zip(owner_tabs, OWNER_FILTERS)):
    with owner_tab:
        idxmap = [(i, fd) for i, fd in enumerate(fds)
                  if owner_filter is None or fd.get("owner") == owner_filter]
        subset = [fd for _, fd in idxmap]

        if subset:
            rows, total_inr = [], 0.0
            for fd in subset:
                curr    = fd.get("currency", "INR")
                amt     = float(fd.get("amount", 0))
                mat_amt = float(fd.get("maturity_amount", 0))
                rate    = _inr_rate(curr)
                equiv   = round(amt * rate, 2)
                mat_inr = round(mat_amt * rate, 2)
                total_inr += equiv
                ref = f"{fd.get('owner','')}|{fd.get('bank','')}|{fd.get('fd_no','')}"
                rows.append({
                    "☑":                  False,
                    "Bank":               _blank(fd.get("bank")),
                    "FD No":              _blank(fd.get("fd_no")),
                    "Owner":              _blank(fd.get("owner")),
                    "Nom":                "✓" if ref in nom_map else "✗",
                    "Currency":           _blank(curr),
                    "Amount":             f"{amt:,.2f}",
                    "Equiv INR":          f"₹ {equiv:,.2f}",
                    "Rate % p.a.":        f"{float(fd.get('rate_pa', 0)):.2f}%",
                    "Start Date":         fmt_date(fd.get("start_date")),
                    "Maturity Date":      fmt_date(fd.get("maturity_date")),
                    "Maturity Amount":    f"{mat_amt:,.2f}",
                    "Maturity INR":       f"₹ {mat_inr:,.2f}",
                })

            df = pd.DataFrame(rows)
            edited = st.data_editor(
                df,
                column_config={
                    "☑":   st.column_config.CheckboxColumn("☑", width="small"),
                    "Nom": st.column_config.TextColumn("Nom", width="small"),
                },
                disabled=[c for c in df.columns if c != "☑"],
                hide_index=True, use_container_width=True,
                key=f"de_fd_{oi}",
            )
            st.caption(f"**Total Equiv INR: ₹ {total_inr:,.2f}**")

            if st.button("🗑️ Delete Selected", key=f"del_fd_{oi}"):
                sel = edited[edited["☑"]].index.tolist()
                if sel:
                    for j in sorted(sel, reverse=True):
                        fds.pop(idxmap[j][0])
                    save("fixed_deposits.json", fds)
                    st.success(f"✅ {len(sel)} FD(s) removed.")
                    st.rerun()
                else:
                    st.warning("Select at least one row to delete.")

            with st.expander("✏️ Quick Edit"):
                qe_rows = [{"Bank": fd.get("bank",""), "FD No": fd.get("fd_no",""),
                            "Amount": float(fd.get("amount", 0)),
                            "Rate % p.a.": float(fd.get("rate_pa", 0)),
                            "Maturity Amount": float(fd.get("maturity_amount", 0))} for fd in subset]
                qe_ed = st.data_editor(
                    pd.DataFrame(qe_rows),
                    column_config={
                        "Bank":            st.column_config.TextColumn(disabled=True),
                        "FD No":           st.column_config.TextColumn(disabled=True),
                        "Amount":          st.column_config.NumberColumn(format="%.2f", min_value=0.0),
                        "Rate % p.a.":     st.column_config.NumberColumn(format="%.2f", min_value=0.0),
                        "Maturity Amount": st.column_config.NumberColumn(format="%.2f", min_value=0.0),
                    },
                    hide_index=True, use_container_width=True, key=f"qe_fd_{oi}",
                )
                if st.button("💾 Save Changes", key=f"qsave_fd_{oi}"):
                    for j, (fi, _) in enumerate(idxmap):
                        fds[fi]["amount"]          = float(qe_ed.iloc[j]["Amount"])
                        fds[fi]["rate_pa"]         = float(qe_ed.iloc[j]["Rate % p.a."])
                        fds[fi]["maturity_amount"] = float(qe_ed.iloc[j]["Maturity Amount"])
                    save("fixed_deposits.json", fds)
                    st.success("✅ Changes saved.")
                    st.rerun()
        else:
            st.info(f"No fixed deposits for {owner_filter or 'any owner'} yet.")

        st.divider()

        # ── ADD ───────────────────────────────────────────────────────────────
        with st.expander("➕ Add Fixed Deposit"):
            with st.form(f"add_fd_{oi}"):
                c1, c2, c3 = st.columns(3)
                bank     = c1.text_input("Bank")
                fd_no    = c2.text_input("FD No")
                if owner_filter:
                    c3.markdown(f"**Owner:** {owner_filter}")
                    owner = owner_filter
                else:
                    owner = c3.selectbox("Owner", OWNERS)
                c4, c5, c6 = st.columns(3)
                currency = c4.selectbox("Currency", CURRENCIES)
                amount   = c5.number_input("Amount", min_value=0.0, step=1000.0, format="%.2f")
                rate_pa  = c6.number_input("Rate % p.a.", min_value=0.0, step=0.01, format="%.2f")
                c7, c8 = st.columns(2)
                start_date    = c7.date_input("Start Date",    value=datetime.date.today(), format="DD/MM/YYYY")
                maturity_date = c8.date_input("Maturity Date", value=datetime.date.today(), format="DD/MM/YYYY")
                maturity_amount = st.number_input("Maturity Amount", min_value=0.0, step=1000.0, format="%.2f")
                nom_name, nom_pct, nom_rel, nom_reg, nom_notes = _nom_section(f"add_fd_{oi}")
                if st.form_submit_button("Add FD"):
                    if not bank.strip():
                        st.error("Bank name is required.")
                    else:
                        fds.append({
                            "bank":            bank.strip(),
                            "fd_no":           fd_no.strip(),
                            "owner":           owner,
                            "currency":        currency,
                            "amount":          amount,
                            "rate_pa":         rate_pa,
                            "start_date":      str(start_date),
                            "maturity_date":   str(maturity_date),
                            "maturity_amount": maturity_amount,
                        })
                        save("fixed_deposits.json", fds)
                        if nom_name:
                            asset_ref = f"{owner}|{bank.strip()}|{fd_no.strip()}"
                            save_nominee("fd", asset_ref, owner,
                                         f"{owner} — {bank.strip()} FD {fd_no.strip()}",
                                         nom_name, nom_pct, nom_rel, nom_reg, nom_notes.strip())
                        st.success(f"✅ FD at {bank} added.")
                        st.rerun()

        # ── EDIT ──────────────────────────────────────────────────────────────
        if subset:
            with st.expander("✏️ Edit Fixed Deposit"):
                opts = [f"{fd.get('bank','—')} — {fd.get('fd_no','—')} ({fd.get('owner','—')})"
                        for fd in subset]
                sel  = st.selectbox("Select FD", opts, key=f"edit_fd_sel_{oi}")
                si   = opts.index(sel)
                fd   = subset[si]
                fi   = idxmap[si][0]
                asset_ref_cur = f"{fd.get('owner','')}|{fd.get('bank','')}|{fd.get('fd_no','')}"
                existing_nom  = nom_map.get(asset_ref_cur)
                with st.form(f"edit_fd_{oi}"):
                    c1, c2, c3 = st.columns(3)
                    bank     = c1.text_input("Bank",  value=fd.get("bank",""))
                    fd_no    = c2.text_input("FD No", value=fd.get("fd_no",""))
                    if owner_filter:
                        c3.markdown(f"**Owner:** {owner_filter}")
                        owner = owner_filter
                    else:
                        oi2   = OWNERS.index(fd.get("owner","Vinay")) if fd.get("owner") in OWNERS else 0
                        owner = c3.selectbox("Owner", OWNERS, index=oi2)
                    c4, c5, c6 = st.columns(3)
                    ci       = CURRENCIES.index(fd.get("currency","INR")) if fd.get("currency") in CURRENCIES else 0
                    currency = c4.selectbox("Currency", CURRENCIES, index=ci)
                    amount   = c5.number_input("Amount",      value=float(fd.get("amount",0)),
                                               min_value=0.0, step=1000.0, format="%.2f")
                    rate_pa  = c6.number_input("Rate % p.a.", value=float(fd.get("rate_pa",0)),
                                               min_value=0.0, step=0.01, format="%.2f")
                    c7, c8 = st.columns(2)
                    start_date    = c7.date_input("Start Date",    value=parse_date(fd.get("start_date"))    or datetime.date.today(), format="DD/MM/YYYY", key=f"edit_fd_sd_{oi}")
                    maturity_date = c8.date_input("Maturity Date", value=parse_date(fd.get("maturity_date")) or datetime.date.today(), format="DD/MM/YYYY", key=f"edit_fd_md_{oi}")
                    maturity_amount = st.number_input("Maturity Amount", value=float(fd.get("maturity_amount",0)),
                                                      min_value=0.0, step=1000.0, format="%.2f")
                    nom_name, nom_pct, nom_rel, nom_reg, nom_notes = _nom_section(f"edit_fd_{oi}", existing_nom)
                    if st.form_submit_button("Save Changes"):
                        fds[fi] = {
                            "bank":            bank.strip(),
                            "fd_no":           fd_no.strip(),
                            "owner":           owner,
                            "currency":        currency,
                            "amount":          amount,
                            "rate_pa":         rate_pa,
                            "start_date":      str(start_date),
                            "maturity_date":   str(maturity_date),
                            "maturity_amount": maturity_amount,
                        }
                        save("fixed_deposits.json", fds)
                        new_ref = f"{owner}|{bank.strip()}|{fd_no.strip()}"
                        save_nominee("fd", new_ref, owner,
                                     f"{owner} — {bank.strip()} FD {fd_no.strip()}",
                                     nom_name, nom_pct, nom_rel, nom_reg, nom_notes.strip())
                        st.success("✅ Changes saved.")
                        st.rerun()
