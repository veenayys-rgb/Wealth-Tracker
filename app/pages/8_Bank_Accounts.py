"""Bank Accounts — India & UAE. Owner tabs + checkbox delete."""
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

OWNERS         = ["Vinay", "Harsh", "Anusha"]
ACCT_TYPES_IN  = ["Savings", "Current", "NRE", "NRO"]
ACCT_TYPES_UAE = ["Savings", "Current", "Fixed", "Other"]
OWNER_LABELS   = ["👤 Vinay", "👤 Harsh", "👤 Anusha", "🏠 All"]
OWNER_FILTERS  = OWNERS + [None]


def _blank(v):
    return v if v else "—"


# ── India ─────────────────────────────────────────────────────────────────────
with tab_india:
    india = load("bank_india.json")
    owner_tabs = st.tabs(OWNER_LABELS)

    for oi, (owner_tab, owner_filter) in enumerate(zip(owner_tabs, OWNER_FILTERS)):
        with owner_tab:
            idxmap = [(i, b) for i, b in enumerate(india)
                      if owner_filter is None or b.get("owner") == owner_filter]
            subset = [b for _, b in idxmap]

            if subset:
                rows, total_bal = [], 0.0
                for b in subset:
                    bal = float(b.get("balance", 0))
                    total_bal += bal
                    rows.append({
                        "☑":                   False,
                        "Bank Name":            _blank(b.get("bank_name")),
                        "Account Type":         _blank(b.get("account_type")),
                        "Account No. (last 4)": _blank(b.get("account_no_last4")),
                        "IFSC":                 _blank(b.get("ifsc")),
                        "Owner":                _blank(b.get("owner")),
                        "2nd Holder":           _blank(b.get("second_holder")),
                        "Balance (₹)":          bal,
                    })
                df = pd.DataFrame(rows)
                edited = st.data_editor(
                    df,
                    column_config={
                        "☑":          st.column_config.CheckboxColumn("☑", width="small"),
                        "Balance (₹)": st.column_config.NumberColumn(format="₹ {:,.2f}"),
                    },
                    disabled=[c for c in df.columns if c != "☑"],
                    hide_index=True, use_container_width=True,
                    key=f"de_india_{oi}",
                )
                st.caption(f"**Total: ₹ {total_bal:,.2f}**")

                if st.button("🗑️ Delete Selected", key=f"del_india_{oi}"):
                    sel = edited[edited["☑"]].index.tolist()
                    if sel:
                        for j in sorted(sel, reverse=True):
                            india.pop(idxmap[j][0])
                        save("bank_india.json", india)
                        st.success(f"✅ {len(sel)} account(s) removed.")
                        st.rerun()
                    else:
                        st.warning("Select at least one row to delete.")
            else:
                st.info(f"No India accounts for {owner_filter or 'any owner'} yet.")

            st.divider()

            # ── ADD ───────────────────────────────────────────────────────────
            with st.expander("➕ Add India Account"):
                with st.form(f"add_bank_india_{oi}"):
                    c1, c2 = st.columns(2)
                    bank_name    = c1.text_input("Bank Name")
                    account_type = c2.selectbox("Account Type", ACCT_TYPES_IN)
                    c3, c4 = st.columns(2)
                    acct_last4   = c3.text_input("Account No. (last 4 digits)")
                    ifsc         = c4.text_input("IFSC Code")
                    c5, c6 = st.columns(2)
                    if owner_filter:
                        c5.markdown(f"**Owner:** {owner_filter}")
                        owner = owner_filter
                    else:
                        owner = c5.selectbox("Owner", OWNERS)
                    second_holder = c6.text_input("2nd Account Holder (optional)")
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
                                "owner":            owner,
                                "second_holder":    second_holder.strip(),
                                "balance":          balance,
                            })
                            save("bank_india.json", india)
                            st.success(f"✅ {bank_name} ({account_type}) added.")
                            st.rerun()

            # ── EDIT ──────────────────────────────────────────────────────────
            if subset:
                with st.expander("✏️ Edit India Account"):
                    opts = [f"{b['bank_name']} ({b.get('account_type','')}) — {b.get('owner','')}"
                            for b in subset]
                    sel  = st.selectbox("Select account", opts, key=f"edit_india_sel_{oi}")
                    si   = opts.index(sel)
                    b    = subset[si]
                    fi   = idxmap[si][0]
                    with st.form(f"edit_bank_india_{oi}"):
                        c1, c2 = st.columns(2)
                        bank_name    = c1.text_input("Bank Name",   value=b.get("bank_name",""))
                        at_idx       = ACCT_TYPES_IN.index(b.get("account_type","Savings")) if b.get("account_type") in ACCT_TYPES_IN else 0
                        account_type = c2.selectbox("Account Type", ACCT_TYPES_IN, index=at_idx)
                        c3, c4 = st.columns(2)
                        acct_last4   = c3.text_input("Account No. (last 4)", value=b.get("account_no_last4",""))
                        ifsc         = c4.text_input("IFSC Code", value=b.get("ifsc",""))
                        c5, c6 = st.columns(2)
                        if owner_filter:
                            c5.markdown(f"**Owner:** {owner_filter}")
                            owner = owner_filter
                        else:
                            oi2   = OWNERS.index(b.get("owner","Vinay")) if b.get("owner") in OWNERS else 0
                            owner = c5.selectbox("Owner", OWNERS, index=oi2)
                        second_holder = c6.text_input("2nd Account Holder", value=b.get("second_holder",""))
                        balance = st.number_input("Current Balance (₹)", value=float(b.get("balance",0)),
                                                  min_value=0.0, step=100.0, format="%.2f")
                        if st.form_submit_button("Save Changes"):
                            india[fi] = {
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


# ── UAE ───────────────────────────────────────────────────────────────────────
with tab_uae:
    uae = load("bank_uae.json")
    owner_tabs_u = st.tabs(OWNER_LABELS)

    for oi, (owner_tab, owner_filter) in enumerate(zip(owner_tabs_u, OWNER_FILTERS)):
        with owner_tab:
            idxmap = [(i, b) for i, b in enumerate(uae)
                      if owner_filter is None or b.get("owner") == owner_filter]
            subset = [b for _, b in idxmap]

            if subset:
                rows, total_aed, total_inr = [], 0.0, 0.0
                for b in subset:
                    bal_aed = float(b.get("balance_aed", 0))
                    equiv   = round(bal_aed * aed, 2)
                    total_aed += bal_aed
                    total_inr += equiv
                    rows.append({
                        "☑":             False,
                        "Bank Name":     _blank(b.get("bank_name")),
                        "Currency":      _blank(b.get("currency")),
                        "Account Type":  _blank(b.get("account_type")),
                        "Account No.":   _blank(b.get("account_no")),
                        "Owner":         _blank(b.get("owner")),
                        "Balance (AED)": bal_aed,
                        "Equiv. INR":    equiv,
                    })
                df = pd.DataFrame(rows)
                edited = st.data_editor(
                    df,
                    column_config={
                        "☑":             st.column_config.CheckboxColumn("☑", width="small"),
                        "Balance (AED)": st.column_config.NumberColumn(format="{:,.2f}"),
                        "Equiv. INR":    st.column_config.NumberColumn(format="₹ {:,.2f}"),
                    },
                    disabled=[c for c in df.columns if c != "☑"],
                    hide_index=True, use_container_width=True,
                    key=f"de_uae_{oi}",
                )
                st.caption(f"**Total: AED {total_aed:,.2f}  ≈  ₹ {total_inr:,.2f}**")

                if st.button("🗑️ Delete Selected", key=f"del_uae_{oi}"):
                    sel = edited[edited["☑"]].index.tolist()
                    if sel:
                        for j in sorted(sel, reverse=True):
                            uae.pop(idxmap[j][0])
                        save("bank_uae.json", uae)
                        st.success(f"✅ {len(sel)} account(s) removed.")
                        st.rerun()
                    else:
                        st.warning("Select at least one row to delete.")
            else:
                st.info(f"No UAE accounts for {owner_filter or 'any owner'} yet.")

            st.divider()

            # ── ADD ───────────────────────────────────────────────────────────
            with st.expander("➕ Add UAE Account"):
                with st.form(f"add_bank_uae_{oi}"):
                    c1, c2 = st.columns(2)
                    bank_name    = c1.text_input("Bank Name")
                    account_type = c2.selectbox("Account Type", ACCT_TYPES_UAE)
                    c3, c4 = st.columns(2)
                    account_no   = c3.text_input("Account No.")
                    currency     = c4.selectbox("Currency", ["AED","USD","EUR","GBP","Other"])
                    c5, c6 = st.columns(2)
                    if owner_filter:
                        c5.markdown(f"**Owner:** {owner_filter}")
                        owner = owner_filter
                    else:
                        owner = c5.selectbox("Owner", OWNERS)
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

            # ── EDIT ──────────────────────────────────────────────────────────
            if subset:
                with st.expander("✏️ Edit UAE Account"):
                    opts = [f"{b['bank_name']} ({b.get('account_type','')}) — {b.get('owner','')}"
                            for b in subset]
                    sel  = st.selectbox("Select account", opts, key=f"edit_uae_sel_{oi}")
                    si   = opts.index(sel)
                    b    = subset[si]
                    fi   = idxmap[si][0]
                    with st.form(f"edit_bank_uae_{oi}"):
                        c1, c2 = st.columns(2)
                        bank_name    = c1.text_input("Bank Name",   value=b.get("bank_name",""))
                        at_idx       = ACCT_TYPES_UAE.index(b.get("account_type","Savings")) if b.get("account_type") in ACCT_TYPES_UAE else 0
                        account_type = c2.selectbox("Account Type", ACCT_TYPES_UAE, index=at_idx)
                        c3, c4 = st.columns(2)
                        account_no   = c3.text_input("Account No.",  value=b.get("account_no",""))
                        curr_opts    = ["AED","USD","EUR","GBP","Other"]
                        ci           = curr_opts.index(b.get("currency","AED")) if b.get("currency") in curr_opts else 0
                        currency     = c4.selectbox("Currency", curr_opts, index=ci)
                        c5, c6 = st.columns(2)
                        if owner_filter:
                            c5.markdown(f"**Owner:** {owner_filter}")
                            owner = owner_filter
                        else:
                            oi2   = OWNERS.index(b.get("owner","Vinay")) if b.get("owner") in OWNERS else 0
                            owner = c5.selectbox("Owner", OWNERS, index=oi2)
                        balance_aed  = c6.number_input("Balance (AED)", value=float(b.get("balance_aed",0)),
                                                       min_value=0.0, step=100.0, format="%.2f")
                        if st.form_submit_button("Save Changes"):
                            uae[fi] = {
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
