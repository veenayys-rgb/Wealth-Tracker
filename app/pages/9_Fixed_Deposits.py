"""Fixed Deposits — India & UAE. Owner tabs + checkbox delete."""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
import pandas as pd
from utils.db     import get_forex
from utils.config import load, save

st.set_page_config(page_title="Fixed Deposits | Wealth Tracker", page_icon="🏛️", layout="wide")
st.title("🏛️ Fixed Deposits")
render_sidebar()

forex = get_forex()
aed   = forex.get("AED_INR", 0)
usd   = forex.get("USD_INR", 0)
st.caption(f"AED/INR: {aed:.4f}  |  USD/INR: {usd:.4f}")

fds = load("fixed_deposits.json")

OWNERS       = ["Vinay", "Harsh", "Anusha", "Mom"]
CURRENCIES   = ["INR", "AED", "USD", "GBP", "EUR", "Other"]
OWNER_LABELS = ["👤 Vinay", "👤 Harsh", "👤 Anusha", "👩 Mom", "🏠 All"]
OWNER_FILTERS = OWNERS + [None]


def _blank(v):
    return v if v else "—"


def _inr_rate(curr):
    if curr == "AED": return aed
    if curr == "USD": return usd
    return 1.0


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
                rows.append({
                    "☑":                  False,
                    "Bank":               _blank(fd.get("bank")),
                    "FD No":              _blank(fd.get("fd_no")),
                    "Owner":              _blank(fd.get("owner")),
                    "Currency":           _blank(curr),
                    "Amount":             f"{amt:,.2f}",
                    "Equiv INR":          f"₹ {equiv:,.2f}",
                    "Rate % p.a.":        f"{float(fd.get('rate_pa', 0)):.2f}%",
                    "Start Date":         _blank(fd.get("start_date")),
                    "Maturity Date":      _blank(fd.get("maturity_date")),
                    "Maturity Amount":    f"{mat_amt:,.2f}",
                    "Maturity INR":       f"₹ {mat_inr:,.2f}",
                })

            df = pd.DataFrame(rows)
            edited = st.data_editor(
                df,
                column_config={"☑": st.column_config.CheckboxColumn("☑", width="small")},
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
                start_date    = c7.date_input("Start Date",    value=datetime.date.today())
                maturity_date = c8.date_input("Maturity Date", value=datetime.date.today())
                maturity_amount = st.number_input("Maturity Amount", min_value=0.0, step=1000.0, format="%.2f")
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
                    try:    sd = datetime.date.fromisoformat(fd.get("start_date","2024-01-01"))
                    except: sd = datetime.date.today()
                    try:    md = datetime.date.fromisoformat(fd.get("maturity_date","2024-01-01"))
                    except: md = datetime.date.today()
                    start_date    = c7.date_input("Start Date",    value=sd, key=f"edit_fd_sd_{oi}")
                    maturity_date = c8.date_input("Maturity Date", value=md, key=f"edit_fd_md_{oi}")
                    maturity_amount = st.number_input("Maturity Amount", value=float(fd.get("maturity_amount",0)),
                                                      min_value=0.0, step=1000.0, format="%.2f")
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
                        st.success("✅ Changes saved.")
                        st.rerun()
