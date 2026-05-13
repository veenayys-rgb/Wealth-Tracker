"""Insurance — all policy types. Highlights upcoming premium due dates. Full Add/Edit/Delete."""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from utils.config import load, save

st.set_page_config(page_title="Insurance | Wealth Tracker", page_icon="🛡️", layout="wide")
st.title("🛡️ Insurance")

policies = load("insurance.json")
today    = datetime.date.today()

OWNERS     = ["Vinay", "Harsh", "Anusha"]
INS_TYPES  = ["Term Life", "Endowment", "ULIP", "Health", "Other"]
CURRENCIES = ["INR", "AED", "USD", "GBP", "EUR", "Other"]

if policies:
    soon = [p for p in policies
            if p.get("next_premium_due") and
            (datetime.date.fromisoformat(p["next_premium_due"]) - today).days <= 30]
    if soon:
        names = ", ".join(p["company_name"] for p in soon)
        st.warning(f"⚠️  {len(soon)} premium(s) due within 30 days: {names}")

    rows = []
    for p in policies:
        due_str = p.get("next_premium_due", "")
        try:
            due_date  = datetime.date.fromisoformat(due_str)
            days_left = (due_date - today).days
            due_label = f"{due_str}  ({days_left}d)" if days_left <= 30 else due_str
        except Exception:
            due_label = due_str

        rows.append({
            "Company Name":         p.get("company_name", ""),
            "Insurance Type":       p.get("insurance_type", ""),
            "Policy No":            p.get("policy_no", ""),
            "Owner":                p.get("owner", ""),
            "Beneficiary":          p.get("beneficiary", ""),
            "Currency":             p.get("currency", "INR"),
            "Insured Value":        float(p.get("insured_value", 0)),
            "Surrender Value":      float(p.get("surrender_value", 0)),
            "Premium Amount":       float(p.get("premium_amount", 0)),
            "Premium Payment Term": p.get("premium_payment_term", ""),
            "Years Premium Paid":   p.get("years_paid", ""),
            "Premium Paid YTD":     float(p.get("premium_paid_ytd", 0)),
            "Next Premium Due":     due_label,
            "Maturity Date":        p.get("maturity_date", ""),
        })

    df = pd.DataFrame(rows)
    fmt = {
        "Insured Value":    "{:,.2f}",
        "Surrender Value":  "{:,.2f}",
        "Premium Amount":   "{:,.2f}",
        "Premium Paid YTD": "{:,.2f}",
    }

    def highlight_due(row):
        if isinstance(row["Next Premium Due"], str) and "d)" in row["Next Premium Due"]:
            return ["background-color: #fff3cd"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df.style.format(fmt).apply(highlight_due, axis=1),
        use_container_width=True, hide_index=True,
    )
else:
    st.info("No insurance policies yet. Add below.")

st.divider()

# ── ADD ───────────────────────────────────────────────────────────────────────
with st.expander("➕ Add Policy"):
    with st.form("add_ins"):
        c1, c2, c3 = st.columns(3)
        company_name   = c1.text_input("Company Name")
        insurance_type = c2.selectbox("Insurance Type", INS_TYPES)
        policy_no      = c3.text_input("Policy No")
        c4, c5, c6 = st.columns(3)
        owner          = c4.selectbox("Owner",      OWNERS)
        beneficiary    = c5.text_input("Beneficiary")
        currency       = c6.selectbox("Currency",   CURRENCIES)
        c7, c8, c9 = st.columns(3)
        insured_value  = c7.number_input("Insured Value",   min_value=0.0, step=1000.0, format="%.2f")
        surrender_value = c8.number_input("Surrender Value", min_value=0.0, step=1000.0, format="%.2f")
        premium_amount = c9.number_input("Premium Amount",  min_value=0.0, step=100.0,  format="%.2f")
        c10, c11, c12 = st.columns(3)
        prem_term      = c10.text_input("Premium Payment Term (e.g. 10 years)")
        years_paid     = c11.text_input("Years Premium Paid")
        prem_ytd       = c12.number_input("Premium Paid YTD", min_value=0.0, step=100.0, format="%.2f")
        c13, c14 = st.columns(2)
        next_due       = c13.date_input("Next Premium Due", value=datetime.date.today())
        try_mat = datetime.date(today.year + 1, today.month, today.day)
        maturity_date  = c14.date_input("Maturity Date",    value=try_mat)
        if st.form_submit_button("Add Policy"):
            if not company_name.strip():
                st.error("Company Name is required.")
            else:
                policies.append({
                    "company_name":        company_name.strip(),
                    "insurance_type":      insurance_type,
                    "policy_no":           policy_no.strip(),
                    "owner":               owner,
                    "beneficiary":         beneficiary.strip(),
                    "currency":            currency,
                    "insured_value":       insured_value,
                    "surrender_value":     surrender_value,
                    "premium_amount":      premium_amount,
                    "premium_payment_term": prem_term.strip(),
                    "years_paid":          years_paid.strip(),
                    "premium_paid_ytd":    prem_ytd,
                    "next_premium_due":    str(next_due),
                    "maturity_date":       str(maturity_date),
                })
                save("insurance.json", policies)
                st.success(f"✅ {company_name} policy added.")
                st.rerun()

# ── EDIT ──────────────────────────────────────────────────────────────────────
if policies:
    with st.expander("✏️ Edit Policy"):
        options = [f"{p.get('policy_no','—')} — {p.get('company_name','')} ({p.get('owner','')})"
                   for p in policies]
        sel     = st.selectbox("Select policy", options, key="edit_ins_sel")
        idx     = options.index(sel)
        p       = policies[idx]
        with st.form("edit_ins"):
            c1, c2, c3 = st.columns(3)
            company_name   = c1.text_input("Company Name",    value=p.get("company_name",""))
            ins_idx        = INS_TYPES.index(p.get("insurance_type","Other")) if p.get("insurance_type") in INS_TYPES else 4
            insurance_type = c2.selectbox("Insurance Type", INS_TYPES, index=ins_idx)
            policy_no      = c3.text_input("Policy No",       value=p.get("policy_no",""))
            c4, c5, c6 = st.columns(3)
            owner_idx      = OWNERS.index(p.get("owner","Vinay")) if p.get("owner") in OWNERS else 0
            owner          = c4.selectbox("Owner", OWNERS,     index=owner_idx)
            beneficiary    = c5.text_input("Beneficiary",     value=p.get("beneficiary",""))
            curr_idx       = CURRENCIES.index(p.get("currency","INR")) if p.get("currency") in CURRENCIES else 0
            currency       = c6.selectbox("Currency", CURRENCIES, index=curr_idx)
            c7, c8, c9 = st.columns(3)
            insured_value  = c7.number_input("Insured Value",    value=float(p.get("insured_value",0)),
                                             min_value=0.0, step=1000.0, format="%.2f")
            surrender_value = c8.number_input("Surrender Value", value=float(p.get("surrender_value",0)),
                                              min_value=0.0, step=1000.0, format="%.2f")
            premium_amount = c9.number_input("Premium Amount",   value=float(p.get("premium_amount",0)),
                                             min_value=0.0, step=100.0, format="%.2f")
            c10, c11, c12 = st.columns(3)
            prem_term      = c10.text_input("Premium Payment Term", value=p.get("premium_payment_term",""))
            years_paid     = c11.text_input("Years Premium Paid",   value=str(p.get("years_paid","")))
            prem_ytd       = c12.number_input("Premium Paid YTD",   value=float(p.get("premium_paid_ytd",0)),
                                              min_value=0.0, step=100.0, format="%.2f")
            c13, c14 = st.columns(2)
            try:    nd = datetime.date.fromisoformat(p.get("next_premium_due","2024-01-01"))
            except: nd = datetime.date.today()
            try:    mat = datetime.date.fromisoformat(p.get("maturity_date","2025-01-01"))
            except: mat = datetime.date.today()
            next_due      = c13.date_input("Next Premium Due", value=nd,  key="edit_ins_nd")
            maturity_date = c14.date_input("Maturity Date",    value=mat, key="edit_ins_mat")
            if st.form_submit_button("Save Changes"):
                policies[idx] = {
                    "company_name":        company_name.strip(),
                    "insurance_type":      insurance_type,
                    "policy_no":           policy_no.strip(),
                    "owner":               owner,
                    "beneficiary":         beneficiary.strip(),
                    "currency":            currency,
                    "insured_value":       insured_value,
                    "surrender_value":     surrender_value,
                    "premium_amount":      premium_amount,
                    "premium_payment_term": prem_term.strip(),
                    "years_paid":          years_paid.strip(),
                    "premium_paid_ytd":    prem_ytd,
                    "next_premium_due":    str(next_due),
                    "maturity_date":       str(maturity_date),
                }
                save("insurance.json", policies)
                st.success("✅ Changes saved.")
                st.rerun()

    # ── DELETE ────────────────────────────────────────────────────────────────
    with st.expander("🗑️ Delete Policy"):
        options_d = [f"{p.get('policy_no','—')} — {p.get('company_name','')} ({p.get('owner','')})"
                     for p in policies]
        sel_d     = st.selectbox("Select policy to delete", options_d, key="del_ins_sel")
        idx_d     = options_d.index(sel_d)
        st.warning(f"This will permanently remove policy **{policies[idx_d].get('policy_no','')}** "
                   f"({policies[idx_d].get('company_name','')}).")
        if st.button("Confirm Delete", key="del_ins_btn"):
            removed = policies.pop(idx_d)
            save("insurance.json", policies)
            st.success(f"✅ {removed.get('company_name','')} policy removed.")
            st.rerun()
