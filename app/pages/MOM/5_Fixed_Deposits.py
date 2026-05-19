"""Mom Fixed Deposits — India. Display + Quick Edit + Add/Edit/Delete."""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import streamlit as st
from utils.sidebar import render_sidebar
import pandas as pd
from utils.config import load, save

st.set_page_config(page_title="Mom Fixed Deposits | Wealth Tracker", page_icon="🏛️", layout="wide")
st.title("🏛️ Mom — Fixed Deposits")
render_sidebar()

FNAME      = "mom_fixed_deposits.json"
CURRENCIES = ["INR", "USD", "GBP", "EUR", "Other"]

def _blank(v):
    return v if v else "—"

fds = load(FNAME)

if fds:
    rows, total_inr = [], 0.0
    for fd in fds:
        amt     = float(fd.get("amount", 0))
        mat_amt = float(fd.get("maturity_amount", 0))
        total_inr += amt   # INR only for Mom
        rows.append({
            "☑":               False,
            "Bank":            _blank(fd.get("bank")),
            "FD No":           _blank(fd.get("fd_no")),
            "Currency":        _blank(fd.get("currency","INR")),
            "Amount":          f"{amt:,.2f}",
            "Rate % p.a.":     f"{float(fd.get('rate_pa', 0)):.2f}%",
            "Start Date":      _blank(fd.get("start_date")),
            "Maturity Date":   _blank(fd.get("maturity_date")),
            "Maturity Amount": f"{mat_amt:,.2f}",
        })

    df = pd.DataFrame(rows)
    edited = st.data_editor(
        df,
        column_config={"☑": st.column_config.CheckboxColumn("☑", width="small")},
        disabled=[c for c in df.columns if c != "☑"],
        hide_index=True, use_container_width=True, key="de_mom_fd",
    )
    st.caption(f"**Total: ₹ {total_inr:,.2f}**")

    if st.button("🗑️ Delete Selected", key="del_mom_fd"):
        sel = edited[edited["☑"]].index.tolist()
        if sel:
            for j in sorted(sel, reverse=True):
                fds.pop(j)
            save(FNAME, fds)
            st.success(f"✅ {len(sel)} FD(s) removed.")
            st.rerun()
        else:
            st.warning("Select at least one row to delete.")

    with st.expander("✏️ Quick Edit"):
        qe_rows = [{"Bank": fd.get("bank",""), "FD No": fd.get("fd_no",""),
                    "Amount": float(fd.get("amount", 0)),
                    "Rate % p.a.": float(fd.get("rate_pa", 0)),
                    "Maturity Amount": float(fd.get("maturity_amount", 0))} for fd in fds]
        qe_ed = st.data_editor(
            pd.DataFrame(qe_rows),
            column_config={
                "Bank":            st.column_config.TextColumn(disabled=True),
                "FD No":           st.column_config.TextColumn(disabled=True),
                "Amount":          st.column_config.NumberColumn(format="%.2f", min_value=0.0),
                "Rate % p.a.":     st.column_config.NumberColumn(format="%.2f", min_value=0.0),
                "Maturity Amount": st.column_config.NumberColumn(format="%.2f", min_value=0.0),
            },
            hide_index=True, use_container_width=True, key="qe_mom_fd",
        )
        if st.button("💾 Save Changes", key="qsave_mom_fd"):
            for j in range(len(fds)):
                fds[j]["amount"]          = float(qe_ed.iloc[j]["Amount"])
                fds[j]["rate_pa"]         = float(qe_ed.iloc[j]["Rate % p.a."])
                fds[j]["maturity_amount"] = float(qe_ed.iloc[j]["Maturity Amount"])
            save(FNAME, fds)
            st.success("✅ Changes saved.")
            st.rerun()
else:
    st.info("No fixed deposits for Mom yet. Add below.")

st.divider()

# ── Add ────────────────────────────────────────────────────────────────────────
with st.expander("➕ Add Fixed Deposit"):
    with st.form("add_mom_fd"):
        c1, c2, c3 = st.columns(3)
        bank     = c1.text_input("Bank")
        fd_no    = c2.text_input("FD No")
        currency = c3.selectbox("Currency", CURRENCIES)
        c4, c5 = st.columns(2)
        amount  = c4.number_input("Amount",      min_value=0.0, step=1000.0, format="%.2f")
        rate_pa = c5.number_input("Rate % p.a.", min_value=0.0, step=0.01,   format="%.2f")
        c6, c7 = st.columns(2)
        start_date    = c6.date_input("Start Date",    value=datetime.date.today())
        maturity_date = c7.date_input("Maturity Date", value=datetime.date.today())
        maturity_amount = st.number_input("Maturity Amount", min_value=0.0, step=1000.0, format="%.2f")
        if st.form_submit_button("Add FD"):
            if not bank.strip():
                st.error("Bank name is required.")
            else:
                fds.append({
                    "bank":            bank.strip(),
                    "fd_no":           fd_no.strip(),
                    "currency":        currency,
                    "amount":          amount,
                    "rate_pa":         rate_pa,
                    "start_date":      str(start_date),
                    "maturity_date":   str(maturity_date),
                    "maturity_amount": maturity_amount,
                })
                save(FNAME, fds)
                st.success(f"✅ FD at {bank} added.")
                st.rerun()

# ── Edit ───────────────────────────────────────────────────────────────────────
if fds:
    with st.expander("✏️ Edit Fixed Deposit"):
        opts = [f"{fd.get('bank','—')} — {fd.get('fd_no','—')}" for fd in fds]
        sel  = st.selectbox("Select FD", opts, key="edit_mom_fd_sel")
        si   = opts.index(sel)
        fd   = fds[si]
        with st.form("edit_mom_fd"):
            c1, c2, c3 = st.columns(3)
            bank     = c1.text_input("Bank",  value=fd.get("bank",""))
            fd_no    = c2.text_input("FD No", value=fd.get("fd_no",""))
            ci       = CURRENCIES.index(fd.get("currency","INR")) if fd.get("currency") in CURRENCIES else 0
            currency = c3.selectbox("Currency", CURRENCIES, index=ci)
            c4, c5 = st.columns(2)
            amount  = c4.number_input("Amount",      value=float(fd.get("amount",0)),
                                      min_value=0.0, step=1000.0, format="%.2f")
            rate_pa = c5.number_input("Rate % p.a.", value=float(fd.get("rate_pa",0)),
                                      min_value=0.0, step=0.01,   format="%.2f")
            c6, c7 = st.columns(2)
            try:    sd = datetime.date.fromisoformat(fd.get("start_date","2024-01-01"))
            except: sd = datetime.date.today()
            try:    md = datetime.date.fromisoformat(fd.get("maturity_date","2024-01-01"))
            except: md = datetime.date.today()
            start_date    = c6.date_input("Start Date",    value=sd, key="edit_mom_fd_sd")
            maturity_date = c7.date_input("Maturity Date", value=md, key="edit_mom_fd_md")
            maturity_amount = st.number_input("Maturity Amount", value=float(fd.get("maturity_amount",0)),
                                              min_value=0.0, step=1000.0, format="%.2f")
            if st.form_submit_button("Save Changes"):
                fds[si] = {
                    "bank":            bank.strip(),
                    "fd_no":           fd_no.strip(),
                    "currency":        currency,
                    "amount":          amount,
                    "rate_pa":         rate_pa,
                    "start_date":      str(start_date),
                    "maturity_date":   str(maturity_date),
                    "maturity_amount": maturity_amount,
                }
                save(FNAME, fds)
                st.success("✅ Changes saved.")
                st.rerun()
