"""Insurance — all policy types. Owner tabs + checkbox delete + auto-calc total premium."""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
import pandas as pd
from utils.config import load, save

st.set_page_config(page_title="Insurance | Wealth Tracker", page_icon="🛡️", layout="wide")
st.title("🛡️ Insurance")
render_sidebar()

policies = load("insurance.json")
today    = datetime.date.today()

OWNERS       = ["Vinay", "Harsh", "Anusha"]
INS_TYPES    = ["Term Life", "Endowment", "ULIP", "Health", "Other"]
CURRENCIES   = ["INR", "AED", "USD", "GBP", "EUR", "Other"]
OWNER_LABELS = ["👤 Vinay", "👤 Harsh", "👤 Anusha", "🏠 All"]
OWNER_FILTERS = OWNERS + [None]


def _blank(v):
    return v if v else "—"


def _calc_total_premium(premium_amount, years_paid_str):
    """Return premium_amount × years_paid if years_paid is numeric, else None."""
    try:
        years = float(str(years_paid_str).strip())
        return round(premium_amount * years, 2)
    except (ValueError, TypeError):
        return None


def _due_label(due_str):
    if not due_str:
        return "—"
    try:
        due_date  = datetime.date.fromisoformat(due_str)
        days_left = (due_date - today).days
        return f"{due_str}  ({days_left}d)" if days_left <= 30 else due_str
    except Exception:
        return due_str


# ── 30-day banner (across all owners) ────────────────────────────────────────
soon = [p for p in policies
        if p.get("next_premium_due") and
        (datetime.date.fromisoformat(p["next_premium_due"]) - today).days <= 30]
if soon:
    names = ", ".join(p["company_name"] for p in soon)
    st.warning(f"⚠️  {len(soon)} premium(s) due within 30 days: {names}")

owner_tabs = st.tabs(OWNER_LABELS)

for oi, (owner_tab, owner_filter) in enumerate(zip(owner_tabs, OWNER_FILTERS)):
    with owner_tab:
        idxmap = [(i, p) for i, p in enumerate(policies)
                  if owner_filter is None or p.get("owner") == owner_filter]
        subset = [p for _, p in idxmap]

        if subset:
            rows = []
            for p in subset:
                prem_amt = float(p.get("premium_amount", 0))
                total_p  = _calc_total_premium(prem_amt, p.get("years_paid", ""))
                ins_val  = float(p.get("insured_value", 0))
                sur_val  = float(p.get("surrender_value", 0))
                tot_paid = total_p if total_p is not None else float(p.get("premium_paid_ytd", 0))
                rows.append({
                    "☑":                  False,
                    "Company":            _blank(p.get("company_name")),
                    "Type":               _blank(p.get("insurance_type")),
                    "Policy No":          _blank(p.get("policy_no")),
                    "Owner":              _blank(p.get("owner")),
                    "Beneficiary":        _blank(p.get("beneficiary")),
                    "Currency":           _blank(p.get("currency")),
                    "Insured Value":      f"{ins_val:,.2f}",
                    "Surrender Value":    f"{sur_val:,.2f}",
                    "Premium Amount":     f"{prem_amt:,.2f}",
                    "Payment Term":       _blank(p.get("premium_payment_term")),
                    "Years Paid":         _blank(p.get("years_paid")),
                    "Total Premium Paid": f"{tot_paid:,.2f}",
                    "Next Due":           _due_label(p.get("next_premium_due", "")),
                    "Maturity Date":      _blank(p.get("maturity_date")),
                })

            df = pd.DataFrame(rows)
            edited = st.data_editor(
                df,
                column_config={"☑": st.column_config.CheckboxColumn("☑", width="small")},
                disabled=[c for c in df.columns if c != "☑"],
                hide_index=True, use_container_width=True,
                key=f"de_ins_{oi}",
            )

            if st.button("🗑️ Delete Selected", key=f"del_ins_{oi}"):
                sel = edited[edited["☑"]].index.tolist()
                if sel:
                    for j in sorted(sel, reverse=True):
                        policies.pop(idxmap[j][0])
                    save("insurance.json", policies)
                    st.success(f"✅ {len(sel)} policy(ies) removed.")
                    st.rerun()
                else:
                    st.warning("Select at least one row to delete.")

            with st.expander("✏️ Quick Edit"):
                qe_rows = [{"Company": p.get("company_name",""), "Policy No": p.get("policy_no",""),
                            "Surrender Value": float(p.get("surrender_value", 0)),
                            "Years Paid": str(p.get("years_paid", "")),
                            "Next Premium Due": str(p.get("next_premium_due", ""))} for p in subset]
                qe_ed = st.data_editor(
                    pd.DataFrame(qe_rows),
                    column_config={
                        "Company":         st.column_config.TextColumn(disabled=True),
                        "Policy No":       st.column_config.TextColumn(disabled=True),
                        "Surrender Value": st.column_config.NumberColumn(format="%.2f", min_value=0.0),
                        "Years Paid":      st.column_config.TextColumn(),
                        "Next Premium Due": st.column_config.TextColumn(),
                    },
                    hide_index=True, use_container_width=True, key=f"qe_ins_{oi}",
                )
                if st.button("💾 Save Changes", key=f"qsave_ins_{oi}"):
                    for j, (fi, _) in enumerate(idxmap):
                        policies[fi]["surrender_value"]  = float(qe_ed.iloc[j]["Surrender Value"])
                        policies[fi]["years_paid"]       = str(qe_ed.iloc[j]["Years Paid"])
                        policies[fi]["next_premium_due"] = str(qe_ed.iloc[j]["Next Premium Due"])
                        calc = _calc_total_premium(float(policies[fi].get("premium_amount", 0)),
                                                   policies[fi]["years_paid"])
                        if calc is not None:
                            policies[fi]["premium_paid_ytd"] = calc
                    save("insurance.json", policies)
                    st.success("✅ Changes saved.")
                    st.rerun()
        else:
            st.info(f"No insurance policies for {owner_filter or 'any owner'} yet.")

        st.divider()

        # ── ADD ───────────────────────────────────────────────────────────────
        with st.expander("➕ Add Policy"):
            with st.form(f"add_ins_{oi}"):
                c1, c2, c3 = st.columns(3)
                company_name   = c1.text_input("Company Name")
                insurance_type = c2.selectbox("Insurance Type", INS_TYPES)
                policy_no      = c3.text_input("Policy No")
                c4, c5, c6 = st.columns(3)
                if owner_filter:
                    c4.markdown(f"**Owner:** {owner_filter}")
                    owner = owner_filter
                else:
                    owner = c4.selectbox("Owner", OWNERS)
                beneficiary = c5.text_input("Beneficiary")
                currency    = c6.selectbox("Currency", CURRENCIES)
                c7, c8, c9 = st.columns(3)
                insured_value   = c7.number_input("Insured Value",   min_value=0.0, step=1000.0, format="%.2f")
                surrender_value = c8.number_input("Surrender Value", min_value=0.0, step=1000.0, format="%.2f")
                premium_amount  = c9.number_input("Premium Amount",  min_value=0.0, step=100.0,  format="%.2f")
                c10, c11 = st.columns(2)
                prem_term  = c10.text_input("Premium Payment Term (e.g. 10 years)")
                years_paid = c11.text_input("Years Premium Paid")
                c12, c13 = st.columns(2)
                next_due      = c12.date_input("Next Premium Due", value=datetime.date.today())
                try_mat       = datetime.date(today.year + 1, today.month, today.day)
                maturity_date = c13.date_input("Maturity Date", value=try_mat)
                if st.form_submit_button("Add Policy"):
                    if not company_name.strip():
                        st.error("Company Name is required.")
                    else:
                        calc = _calc_total_premium(premium_amount, years_paid)
                        policies.append({
                            "company_name":         company_name.strip(),
                            "insurance_type":       insurance_type,
                            "policy_no":            policy_no.strip(),
                            "owner":                owner,
                            "beneficiary":          beneficiary.strip(),
                            "currency":             currency,
                            "insured_value":        insured_value,
                            "surrender_value":      surrender_value,
                            "premium_amount":       premium_amount,
                            "premium_payment_term": prem_term.strip(),
                            "years_paid":           years_paid.strip(),
                            "premium_paid_ytd":     calc if calc is not None else 0.0,
                            "next_premium_due":     str(next_due),
                            "maturity_date":        str(maturity_date),
                        })
                        save("insurance.json", policies)
                        st.success(f"✅ {company_name} policy added.")
                        st.rerun()

        # ── EDIT ──────────────────────────────────────────────────────────────
        if subset:
            with st.expander("✏️ Edit Policy"):
                opts = [f"{p.get('policy_no','—')} — {p.get('company_name','')} ({p.get('owner','')})"
                        for p in subset]
                sel  = st.selectbox("Select policy", opts, key=f"edit_ins_sel_{oi}")
                si   = opts.index(sel)
                p    = subset[si]
                fi   = idxmap[si][0]
                with st.form(f"edit_ins_{oi}"):
                    c1, c2, c3 = st.columns(3)
                    company_name   = c1.text_input("Company Name",    value=p.get("company_name",""))
                    ii             = INS_TYPES.index(p.get("insurance_type","Other")) if p.get("insurance_type") in INS_TYPES else 4
                    insurance_type = c2.selectbox("Insurance Type", INS_TYPES, index=ii)
                    policy_no      = c3.text_input("Policy No",       value=p.get("policy_no",""))
                    c4, c5, c6 = st.columns(3)
                    if owner_filter:
                        c4.markdown(f"**Owner:** {owner_filter}")
                        owner = owner_filter
                    else:
                        oi2   = OWNERS.index(p.get("owner","Vinay")) if p.get("owner") in OWNERS else 0
                        owner = c4.selectbox("Owner", OWNERS, index=oi2)
                    beneficiary = c5.text_input("Beneficiary",  value=p.get("beneficiary",""))
                    ci          = CURRENCIES.index(p.get("currency","INR")) if p.get("currency") in CURRENCIES else 0
                    currency    = c6.selectbox("Currency", CURRENCIES, index=ci)
                    c7, c8, c9 = st.columns(3)
                    insured_value   = c7.number_input("Insured Value",    value=float(p.get("insured_value",0)),
                                                      min_value=0.0, step=1000.0, format="%.2f")
                    surrender_value = c8.number_input("Surrender Value",  value=float(p.get("surrender_value",0)),
                                                      min_value=0.0, step=1000.0, format="%.2f")
                    premium_amount  = c9.number_input("Premium Amount",   value=float(p.get("premium_amount",0)),
                                                      min_value=0.0, step=100.0, format="%.2f")
                    c10, c11 = st.columns(2)
                    prem_term  = c10.text_input("Premium Payment Term", value=p.get("premium_payment_term",""))
                    years_paid = c11.text_input("Years Premium Paid",   value=str(p.get("years_paid","")))
                    c12, c13 = st.columns(2)
                    try:    nd  = datetime.date.fromisoformat(p.get("next_premium_due","2024-01-01"))
                    except: nd  = datetime.date.today()
                    try:    mat = datetime.date.fromisoformat(p.get("maturity_date","2025-01-01"))
                    except: mat = datetime.date.today()
                    next_due      = c12.date_input("Next Premium Due", value=nd,  key=f"edit_ins_nd_{oi}")
                    maturity_date = c13.date_input("Maturity Date",    value=mat, key=f"edit_ins_mat_{oi}")
                    if st.form_submit_button("Save Changes"):
                        calc = _calc_total_premium(premium_amount, years_paid)
                        policies[fi] = {
                            "company_name":         company_name.strip(),
                            "insurance_type":       insurance_type,
                            "policy_no":            policy_no.strip(),
                            "owner":                owner,
                            "beneficiary":          beneficiary.strip(),
                            "currency":             currency,
                            "insured_value":        insured_value,
                            "surrender_value":      surrender_value,
                            "premium_amount":       premium_amount,
                            "premium_payment_term": prem_term.strip(),
                            "years_paid":           years_paid.strip(),
                            "premium_paid_ytd":     calc if calc is not None else float(p.get("premium_paid_ytd",0)),
                            "next_premium_due":     str(next_due),
                            "maturity_date":        str(maturity_date),
                        }
                        save("insurance.json", policies)
                        st.success("✅ Changes saved.")
                        st.rerun()
