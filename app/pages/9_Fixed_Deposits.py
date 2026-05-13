"""Fixed Deposits — India & UAE. Full Add/Edit/Delete."""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from utils.db     import get_forex
from utils.config import load, save

st.set_page_config(page_title="Fixed Deposits | Wealth Tracker", page_icon="🏛️", layout="wide")
st.title("🏛️ Fixed Deposits")

forex = get_forex()
aed   = forex.get("AED_INR", 0)
st.caption(f"AED/INR: {aed:.4f}")

fds = load("fixed_deposits.json")

OWNERS     = ["Vinay", "Harsh", "Anusha"]
CURRENCIES = ["INR", "AED", "USD", "GBP", "EUR", "Other"]

if fds:
    rows = []
    total_inr = 0.0
    for fd in fds:
        curr    = fd.get("currency", "INR")
        amt     = float(fd.get("amount", 0))
        mat_amt = float(fd.get("maturity_amount", 0))
        rate    = aed if curr == "AED" else 1.0
        equiv   = round(amt     * rate, 2)
        mat_inr = round(mat_amt * rate, 2)
        total_inr += equiv
        rows.append({
            "Bank":               fd.get("bank", ""),
            "FD No":              fd.get("fd_no", ""),
            "Owner":              fd.get("owner", ""),
            "Currency":           curr,
            "Amount":             amt,
            "Equiv INR":          equiv,
            "Rate % p.a.":        float(fd.get("rate_pa", 0)),
            "Start Date":         fd.get("start_date", ""),
            "Maturity Date":      fd.get("maturity_date", ""),
            "Maturity Amount":    mat_amt,
            "Maturity Equiv INR": mat_inr,
        })
    rows.append({
        "Bank": "TOTAL", "FD No": "", "Owner": "", "Currency": "",
        "Amount": None, "Equiv INR": total_inr, "Rate % p.a.": None,
        "Start Date": "", "Maturity Date": "", "Maturity Amount": None, "Maturity Equiv INR": None,
    })
    df = pd.DataFrame(rows)
    fmt = {
        "Amount":             lambda v: f"{v:,.2f}" if v else "—",
        "Equiv INR":          "₹ {:,.2f}",
        "Rate % p.a.":        lambda v: f"{v:.2f}%" if v else "—",
        "Maturity Amount":    lambda v: f"{v:,.2f}" if v else "—",
        "Maturity Equiv INR": lambda v: f"₹ {v:,.2f}" if v else "—",
    }
    st.dataframe(
        df.style.format(fmt)
          .set_properties(**{"font-weight": "bold"}, subset=pd.IndexSlice[df.index[-1], :]),
        use_container_width=True, hide_index=True,
    )
else:
    st.info("No fixed deposits yet. Add below.")

st.divider()

# ── ADD ───────────────────────────────────────────────────────────────────────
with st.expander("➕ Add Fixed Deposit"):
    with st.form("add_fd"):
        c1, c2, c3 = st.columns(3)
        bank     = c1.text_input("Bank")
        fd_no    = c2.text_input("FD No")
        owner    = c3.selectbox("Owner", OWNERS)
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
                    "bank":             bank.strip(),
                    "fd_no":            fd_no.strip(),
                    "owner":            owner,
                    "currency":         currency,
                    "amount":           amount,
                    "rate_pa":          rate_pa,
                    "start_date":       str(start_date),
                    "maturity_date":    str(maturity_date),
                    "maturity_amount":  maturity_amount,
                })
                save("fixed_deposits.json", fds)
                st.success(f"✅ FD at {bank} added.")
                st.rerun()

# ── EDIT ──────────────────────────────────────────────────────────────────────
if fds:
    with st.expander("✏️ Edit Fixed Deposit"):
        options = [f"{fd.get('bank','')} — {fd.get('fd_no','')} ({fd.get('owner','')})" for fd in fds]
        sel     = st.selectbox("Select FD", options, key="edit_fd_sel")
        idx     = options.index(sel)
        fd      = fds[idx]
        with st.form("edit_fd"):
            c1, c2, c3 = st.columns(3)
            bank     = c1.text_input("Bank",  value=fd.get("bank",""))
            fd_no    = c2.text_input("FD No", value=fd.get("fd_no",""))
            owner_idx = OWNERS.index(fd.get("owner","Vinay")) if fd.get("owner") in OWNERS else 0
            owner    = c3.selectbox("Owner", OWNERS, index=owner_idx)
            c4, c5, c6 = st.columns(3)
            curr_idx  = CURRENCIES.index(fd.get("currency","INR")) if fd.get("currency") in CURRENCIES else 0
            currency  = c4.selectbox("Currency", CURRENCIES, index=curr_idx)
            amount    = c5.number_input("Amount",      value=float(fd.get("amount",0)),
                                        min_value=0.0, step=1000.0, format="%.2f")
            rate_pa   = c6.number_input("Rate % p.a.", value=float(fd.get("rate_pa",0)),
                                        min_value=0.0, step=0.01, format="%.2f")
            c7, c8 = st.columns(2)
            try:    sd = datetime.date.fromisoformat(fd.get("start_date","2024-01-01"))
            except: sd = datetime.date.today()
            try:    md = datetime.date.fromisoformat(fd.get("maturity_date","2024-01-01"))
            except: md = datetime.date.today()
            start_date    = c7.date_input("Start Date",    value=sd, key="edit_fd_sd")
            maturity_date = c8.date_input("Maturity Date", value=md, key="edit_fd_md")
            maturity_amount = st.number_input("Maturity Amount", value=float(fd.get("maturity_amount",0)),
                                              min_value=0.0, step=1000.0, format="%.2f")
            if st.form_submit_button("Save Changes"):
                fds[idx] = {
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

    # ── DELETE ────────────────────────────────────────────────────────────────
    with st.expander("🗑️ Delete Fixed Deposit"):
        options_d = [f"{fd.get('bank','')} — {fd.get('fd_no','')} ({fd.get('owner','')})" for fd in fds]
        sel_d     = st.selectbox("Select FD to delete", options_d, key="del_fd_sel")
        idx_d     = options_d.index(sel_d)
        st.warning(f"This will permanently remove FD **{fds[idx_d].get('fd_no','')}** at {fds[idx_d].get('bank','')}.")
        if st.button("Confirm Delete", key="del_fd_btn"):
            removed = fds.pop(idx_d)
            save("fixed_deposits.json", fds)
            st.success(f"✅ {removed.get('bank','')} FD removed.")
            st.rerun()
