"""Bank Accounts — India & UAE. Full Add/Edit/Delete."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from utils.db     import get_forex
from utils.config import load, save

st.set_page_config(page_title="Bank Accounts | Wealth Tracker", page_icon="🏦", layout="wide")
st.title("🏦 Bank Accounts")

forex = get_forex()
aed   = forex.get("AED_INR", 0)
st.caption(f"AED/INR: {aed:.4f}  (used for UAE balance conversion)")

tab_india, tab_uae = st.tabs(["🇮🇳 India", "🇦🇪 UAE"])

OWNERS       = ["Vinay", "Harsh", "Anusha"]
ACCT_TYPES_IN = ["Savings", "Current", "NRE", "NRO"]
ACCT_TYPES_UAE = ["Savings", "Current", "Fixed", "Other"]

# ── India ─────────────────────────────────────────────────────────────────────
with tab_india:
    india = load("bank_india.json")

    if india:
        rows = []
        total_bal = 0.0
        for b in india:
            bal = float(b.get("balance", 0))
            total_bal += bal
            rows.append({
                "Bank Name":            b.get("bank_name", ""),
                "Account Type":         b.get("account_type", ""),
                "Account No. (last 4)": b.get("account_no_last4", ""),
                "IFSC":                 b.get("ifsc", ""),
                "Owner":                b.get("owner", ""),
                "2nd Account Holder":   b.get("second_holder", ""),
                "Current Balance (₹)":  bal,
            })
        rows.append({
            "Bank Name": "TOTAL", "Account Type": "", "Account No. (last 4)": "",
            "IFSC": "", "Owner": "", "2nd Account Holder": "",
            "Current Balance (₹)": total_bal,
        })
        df = pd.DataFrame(rows)
        st.dataframe(
            df.style.format({"Current Balance (₹)": "₹ {:,.2f}"})
              .set_properties(**{"font-weight": "bold"}, subset=pd.IndexSlice[df.index[-1], :]),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No India bank accounts yet. Add below.")

    st.divider()

    # ── ADD ───────────────────────────────────────────────────────────────────
    with st.expander("➕ Add India Account"):
        with st.form("add_bank_india"):
            c1, c2 = st.columns(2)
            bank_name   = c1.text_input("Bank Name")
            account_type = c2.selectbox("Account Type", ACCT_TYPES_IN)
            c3, c4 = st.columns(2)
            acct_last4  = c3.text_input("Account No. (last 4 digits)")
            ifsc        = c4.text_input("IFSC Code")
            c5, c6 = st.columns(2)
            owner        = c5.selectbox("Owner", OWNERS)
            second_holder = c6.text_input("2nd Account Holder (optional)")
            balance = st.number_input("Current Balance (₹)", min_value=0.0, step=100.0, format="%.2f")
            if st.form_submit_button("Add Account"):
                if not bank_name.strip():
                    st.error("Bank Name is required.")
                else:
                    india.append({
                        "bank_name":       bank_name.strip(),
                        "account_type":    account_type,
                        "account_no_last4": acct_last4.strip(),
                        "ifsc":            ifsc.strip().upper(),
                        "owner":           owner,
                        "second_holder":   second_holder.strip(),
                        "balance":         balance,
                    })
                    save("bank_india.json", india)
                    st.success(f"✅ {bank_name} ({account_type}) added.")
                    st.rerun()

    # ── EDIT ──────────────────────────────────────────────────────────────────
    if india:
        with st.expander("✏️ Edit India Account"):
            options = [f"{b['bank_name']} ({b['account_type']}) — {b.get('owner','')}" for b in india]
            sel     = st.selectbox("Select account", options, key="edit_india_sel")
            idx     = options.index(sel)
            b       = india[idx]
            with st.form("edit_bank_india"):
                c1, c2 = st.columns(2)
                bank_name   = c1.text_input("Bank Name",    value=b.get("bank_name", ""))
                acct_type_idx = ACCT_TYPES_IN.index(b.get("account_type","Savings")) if b.get("account_type") in ACCT_TYPES_IN else 0
                account_type = c2.selectbox("Account Type", ACCT_TYPES_IN, index=acct_type_idx)
                c3, c4 = st.columns(2)
                acct_last4   = c3.text_input("Account No. (last 4)", value=b.get("account_no_last4",""))
                ifsc         = c4.text_input("IFSC Code", value=b.get("ifsc",""))
                c5, c6 = st.columns(2)
                owner_idx    = OWNERS.index(b.get("owner","Vinay")) if b.get("owner") in OWNERS else 0
                owner        = c5.selectbox("Owner", OWNERS, index=owner_idx)
                second_holder = c6.text_input("2nd Account Holder", value=b.get("second_holder",""))
                balance = st.number_input("Current Balance (₹)", value=float(b.get("balance",0)),
                                          min_value=0.0, step=100.0, format="%.2f")
                if st.form_submit_button("Save Changes"):
                    india[idx] = {
                        "bank_name":        bank_name.strip(),
                        "account_type":     account_type,
                        "account_no_last4": acct_last4.strip(),
                        "ifsc":             ifsc.strip().upper(),
                        "owner":            owner,
                        "second_holder":    second_holder.strip(),
                        "balance":          balance,
                    }
                    save("bank_india.json", india)
                    st.success("✅ Changes saved.")
                    st.rerun()

        # ── DELETE ────────────────────────────────────────────────────────────
        with st.expander("🗑️ Delete India Account"):
            options_d = [f"{b['bank_name']} ({b['account_type']}) — {b.get('owner','')}" for b in india]
            sel_d     = st.selectbox("Select account to delete", options_d, key="del_india_sel")
            idx_d     = options_d.index(sel_d)
            st.warning(f"This will permanently remove **{india[idx_d]['bank_name']}** ({india[idx_d]['account_type']}).")
            if st.button("Confirm Delete", key="del_india_btn"):
                removed = india.pop(idx_d)
                save("bank_india.json", india)
                st.success(f"✅ {removed['bank_name']} removed.")
                st.rerun()

# ── UAE ───────────────────────────────────────────────────────────────────────
with tab_uae:
    uae = load("bank_uae.json")

    if uae:
        rows = []
        total_aed = total_inr = 0.0
        for b in uae:
            bal_aed = float(b.get("balance_aed", 0))
            equiv   = round(bal_aed * aed, 2)
            total_aed += bal_aed
            total_inr += equiv
            rows.append({
                "Bank Name":    b.get("bank_name", ""),
                "Currency":     b.get("currency", "AED"),
                "Account Type": b.get("account_type", ""),
                "Account No.":  b.get("account_no", ""),
                "Owner":        b.get("owner", ""),
                "Balance (AED)": bal_aed,
                "Equiv. INR":   equiv,
            })
        rows.append({
            "Bank Name": "TOTAL", "Currency": "", "Account Type": "",
            "Account No.": "", "Owner": "",
            "Balance (AED)": total_aed, "Equiv. INR": total_inr,
        })
        df = pd.DataFrame(rows)
        st.dataframe(
            df.style.format({"Balance (AED)": "{:,.2f}", "Equiv. INR": "₹ {:,.2f}"})
              .set_properties(**{"font-weight": "bold"}, subset=pd.IndexSlice[df.index[-1], :]),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No UAE bank accounts yet. Add below.")

    st.divider()

    # ── ADD ───────────────────────────────────────────────────────────────────
    with st.expander("➕ Add UAE Account"):
        with st.form("add_bank_uae"):
            c1, c2 = st.columns(2)
            bank_name    = c1.text_input("Bank Name")
            account_type = c2.selectbox("Account Type", ACCT_TYPES_UAE)
            c3, c4 = st.columns(2)
            account_no   = c3.text_input("Account No.")
            currency     = c4.selectbox("Currency", ["AED", "USD", "EUR", "GBP", "Other"])
            c5, c6 = st.columns(2)
            owner_idx    = 0
            owner        = c5.selectbox("Owner", OWNERS)
            balance_aed  = c6.number_input("Balance (AED)", min_value=0.0, step=100.0, format="%.2f")
            if st.form_submit_button("Add Account"):
                if not bank_name.strip():
                    st.error("Bank Name is required.")
                else:
                    uae.append({
                        "bank_name":    bank_name.strip(),
                        "currency":     currency,
                        "account_type": account_type,
                        "account_no":   account_no.strip(),
                        "owner":        owner,
                        "balance_aed":  balance_aed,
                    })
                    save("bank_uae.json", uae)
                    st.success(f"✅ {bank_name} added.")
                    st.rerun()

    # ── EDIT ──────────────────────────────────────────────────────────────────
    if uae:
        with st.expander("✏️ Edit UAE Account"):
            options = [f"{b['bank_name']} ({b['account_type']}) — {b.get('owner','')}" for b in uae]
            sel     = st.selectbox("Select account", options, key="edit_uae_sel")
            idx     = options.index(sel)
            b       = uae[idx]
            with st.form("edit_bank_uae"):
                c1, c2 = st.columns(2)
                bank_name    = c1.text_input("Bank Name",    value=b.get("bank_name",""))
                acct_type_idx = ACCT_TYPES_UAE.index(b.get("account_type","Savings")) if b.get("account_type") in ACCT_TYPES_UAE else 0
                account_type = c2.selectbox("Account Type", ACCT_TYPES_UAE, index=acct_type_idx)
                c3, c4 = st.columns(2)
                account_no   = c3.text_input("Account No.",  value=b.get("account_no",""))
                curr_opts    = ["AED","USD","EUR","GBP","Other"]
                curr_idx     = curr_opts.index(b.get("currency","AED")) if b.get("currency") in curr_opts else 0
                currency     = c4.selectbox("Currency", curr_opts, index=curr_idx)
                c5, c6 = st.columns(2)
                owner_idx    = OWNERS.index(b.get("owner","Vinay")) if b.get("owner") in OWNERS else 0
                owner        = c5.selectbox("Owner", OWNERS, index=owner_idx)
                balance_aed  = c6.number_input("Balance (AED)", value=float(b.get("balance_aed",0)),
                                               min_value=0.0, step=100.0, format="%.2f")
                if st.form_submit_button("Save Changes"):
                    uae[idx] = {
                        "bank_name":    bank_name.strip(),
                        "currency":     currency,
                        "account_type": account_type,
                        "account_no":   account_no.strip(),
                        "owner":        owner,
                        "balance_aed":  balance_aed,
                    }
                    save("bank_uae.json", uae)
                    st.success("✅ Changes saved.")
                    st.rerun()

        # ── DELETE ────────────────────────────────────────────────────────────
        with st.expander("🗑️ Delete UAE Account"):
            options_d = [f"{b['bank_name']} ({b['account_type']}) — {b.get('owner','')}" for b in uae]
            sel_d     = st.selectbox("Select account to delete", options_d, key="del_uae_sel")
            idx_d     = options_d.index(sel_d)
            st.warning(f"This will permanently remove **{uae[idx_d]['bank_name']}** ({uae[idx_d]['account_type']}).")
            if st.button("Confirm Delete", key="del_uae_btn"):
                removed = uae.pop(idx_d)
                save("bank_uae.json", uae)
                st.success(f"✅ {removed['bank_name']} removed.")
                st.rerun()
