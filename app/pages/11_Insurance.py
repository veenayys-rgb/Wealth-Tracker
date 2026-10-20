"""Insurance — all policy types. Owner tabs + checkbox delete + auto-calc total premium."""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
import pandas as pd
from utils.config import load, save
from utils.fmt    import fmt_date, parse_date
from utils.db     import fetch_nominees_map, save_nominee, upload_policy_doc, delete_policy_doc

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

_NOMINEES = ["Anusha", "Vinay", "Harsh", "Mom", "Other"]
_RELS     = ["Spouse", "Son", "Daughter", "Father", "Mother", "Brother", "Sister", "Other"]

# Load all insurance nominees once (all owners)
nom_map = fetch_nominees_map("insurance")


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
        due_date  = datetime.date.fromisoformat(str(due_str)[:10])
        days_left = (due_date - today).days
        label = fmt_date(due_str)
        return f"{label}  ({days_left}d)" if days_left <= 30 else label
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
                ref      = f"{p.get('owner','')}|{p.get('policy_no','')}"
                rows.append({
                    "☑":                  False,
                    "Company":            _blank(p.get("company_name")),
                    "Type":               _blank(p.get("insurance_type")),
                    "Policy No":          _blank(p.get("policy_no")),
                    "Owner":              _blank(p.get("owner")),
                    "Beneficiary":        _blank(p.get("beneficiary")),
                    "Nom":                "✓" if ref in nom_map else "✗",
                    "Currency":           _blank(p.get("currency")),
                    "Insured Value":      f"{ins_val:,.2f}",
                    "Surrender Value":    f"{sur_val:,.2f}",
                    "Premium Amount":     f"{prem_amt:,.2f}",
                    "Payment Term":       _blank(p.get("premium_payment_term")),
                    "Years Paid":         _blank(p.get("years_paid")),
                    "Total Premium Paid": f"{tot_paid:,.2f}",
                    "Next Due":           _due_label(p.get("next_premium_due", "")),
                    "Maturity Date":      fmt_date(p.get("maturity_date")),
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
                            "Next Premium Due": parse_date(p.get("next_premium_due", ""))} for p in subset]
                qe_ed = st.data_editor(
                    pd.DataFrame(qe_rows),
                    column_config={
                        "Company":          st.column_config.TextColumn(disabled=True),
                        "Policy No":        st.column_config.TextColumn(disabled=True),
                        "Surrender Value":  st.column_config.NumberColumn(format="%.2f", min_value=0.0),
                        "Years Paid":       st.column_config.TextColumn(),
                        "Next Premium Due": st.column_config.DateColumn(format="DD-MMM-YYYY"),
                    },
                    hide_index=True, use_container_width=True, key=f"qe_ins_{oi}",
                )
                if st.button("💾 Save Changes", key=f"qsave_ins_{oi}"):
                    for j, (fi, _) in enumerate(idxmap):
                        policies[fi]["surrender_value"] = float(qe_ed.iloc[j]["Surrender Value"])
                        policies[fi]["years_paid"]      = str(qe_ed.iloc[j]["Years Paid"])
                        raw_nd = qe_ed.iloc[j]["Next Premium Due"]
                        policies[fi]["next_premium_due"] = raw_nd.isoformat() if isinstance(raw_nd, datetime.date) else (str(raw_nd)[:10] if raw_nd else "")
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
                next_due      = c12.date_input("Next Premium Due", value=datetime.date.today(), format="DD/MM/YYYY")
                try_mat       = datetime.date(today.year + 1, today.month, today.day)
                maturity_date = c13.date_input("Maturity Date",    value=try_mat, format="DD/MM/YYYY")

                st.divider()
                st.markdown("**🎯 Nominee**")
                nc1, nc2, nc3 = st.columns(3)
                nom_name = nc1.selectbox("Nominee Name", [""] + _NOMINEES, key=f"add_nom_name_{oi}")
                nom_pct  = nc2.number_input("Share %", 0.0, 100.0, 100.0, step=1.0, key=f"add_nom_pct_{oi}")
                nom_rel  = nc3.selectbox("Relationship", [""] + _RELS, key=f"add_nom_rel_{oi}")
                nc4, nc5 = st.columns(2)
                nom_reg   = nc4.checkbox("Nomination Registered", key=f"add_nom_reg_{oi}")
                nom_notes = nc5.text_input("Nominee Notes", key=f"add_nom_notes_{oi}", placeholder="(optional)")
                doc_file = st.file_uploader("Upload Policy Doc (PDF/JPG/PNG)", type=["pdf","jpg","jpeg","png"], key=f"add_doc_{oi}")

                if st.form_submit_button("Add Policy"):
                    if not company_name.strip():
                        st.error("Company Name is required.")
                    else:
                        calc = _calc_total_premium(premium_amount, years_paid)
                        doc_url = ""
                        if doc_file:
                            try:
                                doc_url = upload_policy_doc(owner, policy_no.strip() or company_name.strip(),
                                                            doc_file.name, doc_file.read(), doc_file.type)
                            except Exception as e:
                                st.warning(f"Policy doc upload failed: {e}")
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
                            "doc_url":              doc_url,
                        })
                        save("insurance.json", policies)
                        if nom_name:
                            asset_ref = f"{owner}|{policy_no.strip()}"
                            save_nominee("insurance", asset_ref, owner,
                                         f"{owner} — {company_name.strip()} {policy_no.strip()}",
                                         nom_name, nom_pct, nom_rel, nom_reg, nom_notes.strip())
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

                # Load existing nominee for pre-population
                asset_ref_cur = f"{p.get('owner','')}|{p.get('policy_no','')}"
                existing_nom  = nom_map.get(asset_ref_cur)
                cur_doc_url   = (p.get("doc_url") or "").strip()
                if cur_doc_url:
                    dc1, dc2 = st.columns([3, 1])
                    dc1.markdown(f"📄 [View policy document]({cur_doc_url})")
                    if dc2.button("🗑 Remove doc", key=f"rm_doc_{oi}"):
                        delete_policy_doc(cur_doc_url)
                        policies[fi]["doc_url"] = ""
                        save("insurance.json", policies)
                        st.success("✅ Document removed.")
                        st.rerun()

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
                    next_due      = c12.date_input("Next Premium Due", value=parse_date(p.get("next_premium_due")) or datetime.date.today(), format="DD/MM/YYYY", key=f"edit_ins_nd_{oi}")
                    maturity_date = c13.date_input("Maturity Date",    value=parse_date(p.get("maturity_date"))    or datetime.date.today(), format="DD/MM/YYYY", key=f"edit_ins_mat_{oi}")

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
                    nom_name = nc1.selectbox("Nominee Name", [""] + _NOMINEES, index=_nom_idx, key=f"edit_nom_name_{oi}")
                    nom_pct  = nc2.number_input("Share %", 0.0, 100.0, _pct_val, step=1.0, key=f"edit_nom_pct_{oi}")
                    nom_rel  = nc3.selectbox("Relationship", [""] + _RELS, index=_rel_idx, key=f"edit_nom_rel_{oi}")
                    nc4, nc5 = st.columns(2)
                    nom_reg   = nc4.checkbox("Nomination Registered", value=_reg_val, key=f"edit_nom_reg_{oi}")
                    nom_notes = nc5.text_input("Nominee Notes", value=_notes_v, key=f"edit_nom_notes_{oi}")
                    doc_file  = st.file_uploader("Replace Policy Doc (PDF/JPG/PNG)", type=["pdf","jpg","jpeg","png"], key=f"edit_doc_{oi}")

                    if st.form_submit_button("Save Changes"):
                        calc = _calc_total_premium(premium_amount, years_paid)
                        new_doc_url = cur_doc_url
                        if doc_file:
                            try:
                                if cur_doc_url:
                                    delete_policy_doc(cur_doc_url)
                                new_doc_url = upload_policy_doc(owner, policy_no.strip() or company_name.strip(),
                                                                doc_file.name, doc_file.read(), doc_file.type)
                            except Exception as e:
                                st.warning(f"Doc upload failed: {e}")
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
                            "doc_url":              new_doc_url,
                        }
                        save("insurance.json", policies)
                        new_ref = f"{owner}|{policy_no.strip()}"
                        save_nominee("insurance", new_ref, owner,
                                     f"{owner} — {company_name.strip()} {policy_no.strip()}",
                                     nom_name, nom_pct, nom_rel, nom_reg, nom_notes.strip())
                        st.success("✅ Changes saved.")
                        st.rerun()
