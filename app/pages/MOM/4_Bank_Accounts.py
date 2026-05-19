"""Mom Bank Accounts — India only. Display + Quick Edit + Add/Edit/Delete."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import streamlit as st
from utils.sidebar import render_sidebar
import pandas as pd
from utils.config import load, save

st.set_page_config(page_title="Mom Bank Accounts | Wealth Tracker", page_icon="🏦", layout="wide")
st.title("🏦 Mom — Bank Accounts")
render_sidebar()

FNAME      = "mom_bank_india.json"
ACCT_TYPES = ["Savings", "Current", "NRE", "NRO"]

def _blank(v):
    return v if v else "—"

india = load(FNAME)

if india:
    rows, total_bal = [], 0.0
    for b in india:
        bal = float(b.get("balance", 0))
        total_bal += bal
        rows.append({
            "☑":            False,
            "Bank Name":    _blank(b.get("bank_name")),
            "Account Type": _blank(b.get("account_type")),
            "Account No.":  _blank(b.get("account_no_last4")),
            "IFSC":         _blank(b.get("ifsc")),
            "2nd Holder":   _blank(b.get("second_holder")),
            "Balance (₹)":  f"₹ {bal:,.2f}",
        })
    df = pd.DataFrame(rows)
    edited = st.data_editor(
        df,
        column_config={"☑": st.column_config.CheckboxColumn("☑", width="small")},
        disabled=[c for c in df.columns if c != "☑"],
        hide_index=True, use_container_width=True, key="de_mom_india",
    )
    st.caption(f"**Total: ₹ {total_bal:,.2f}**")

    if st.button("🗑️ Delete Selected", key="del_mom_india"):
        sel = edited[edited["☑"]].index.tolist()
        if sel:
            for j in sorted(sel, reverse=True):
                india.pop(j)
            save(FNAME, india)
            st.success(f"✅ {len(sel)} account(s) removed.")
            st.rerun()
        else:
            st.warning("Select at least one row to delete.")

    with st.expander("✏️ Quick Edit — Balance"):
        qe_rows = [{"Bank": b.get("bank_name",""),
                    "Account No.": b.get("account_no_last4",""),
                    "Balance (₹)": float(b.get("balance", 0))} for b in india]
        qe_ed = st.data_editor(
            pd.DataFrame(qe_rows),
            column_config={
                "Bank":        st.column_config.TextColumn(disabled=True),
                "Account No.": st.column_config.TextColumn(),
                "Balance (₹)": st.column_config.NumberColumn(format="%.2f", min_value=0.0),
            },
            hide_index=True, use_container_width=True, key="qe_mom_india",
        )
        if st.button("💾 Save Balances", key="qsave_mom_india"):
            for j in range(len(india)):
                india[j]["account_no_last4"] = str(qe_ed.iloc[j]["Account No."])
                india[j]["balance"]          = float(qe_ed.iloc[j]["Balance (₹)"])
            save(FNAME, india)
            st.success("✅ Balances saved.")
            st.rerun()
else:
    st.info("No bank accounts for Mom yet. Add below.")

st.divider()

# ── Add ────────────────────────────────────────────────────────────────────────
with st.expander("➕ Add Account"):
    with st.form("add_mom_bank"):
        c1, c2 = st.columns(2)
        bank_name    = c1.text_input("Bank Name")
        account_type = c2.selectbox("Account Type", ACCT_TYPES)
        c3, c4 = st.columns(2)
        acct_last4    = c3.text_input("Account No. (last 4 digits)")
        ifsc          = c4.text_input("IFSC Code")
        second_holder = st.text_input("2nd Account Holder (optional)")
        balance = st.number_input("Current Balance (₹)", min_value=0.0, step=100.0, format="%.2f")
        if st.form_submit_button("Add Account"):
            if not bank_name.strip():
                st.error("Bank Name is required.")
            else:
                india.append({
                    "bank_name":        bank_name.strip(),
                    "account_type":     account_type,
                    "account_no_last4": acct_last4.strip(),
                    "ifsc":             ifsc.strip().upper(),
                    "second_holder":    second_holder.strip(),
                    "balance":          balance,
                })
                save(FNAME, india)
                st.success(f"✅ {bank_name} ({account_type}) added.")
                st.rerun()

# ── Edit ───────────────────────────────────────────────────────────────────────
if india:
    with st.expander("✏️ Edit Account"):
        opts = [f"{b['bank_name']} ({b.get('account_type','')}) — {b.get('account_no_last4','')}"
                for b in india]
        sel  = st.selectbox("Select account", opts, key="edit_mom_bank_sel")
        si   = opts.index(sel)
        b    = india[si]
        with st.form("edit_mom_bank"):
            c1, c2 = st.columns(2)
            bank_name    = c1.text_input("Bank Name",   value=b.get("bank_name",""))
            at_idx       = ACCT_TYPES.index(b.get("account_type","Savings")) if b.get("account_type") in ACCT_TYPES else 0
            account_type = c2.selectbox("Account Type", ACCT_TYPES, index=at_idx)
            c3, c4 = st.columns(2)
            acct_last4    = c3.text_input("Account No. (last 4)", value=b.get("account_no_last4",""))
            ifsc          = c4.text_input("IFSC Code",            value=b.get("ifsc",""))
            second_holder = st.text_input("2nd Account Holder",   value=b.get("second_holder",""))
            balance = st.number_input("Current Balance (₹)", value=float(b.get("balance",0)),
                                      min_value=0.0, step=100.0, format="%.2f")
            if st.form_submit_button("Save Changes"):
                india[si] = {
                    "bank_name":        bank_name.strip(),
                    "account_type":     account_type,
                    "account_no_last4": acct_last4.strip(),
                    "ifsc":             ifsc.strip().upper(),
                    "second_holder":    second_holder.strip(),
                    "balance":          balance,
                }
                save(FNAME, india)
                st.success("✅ Changes saved.")
                st.rerun()
