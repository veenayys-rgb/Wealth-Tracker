"""Settings — Nominee information for all asset classes."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd

from utils.sidebar import render_sidebar
from utils.db      import fetch, service_insert, service_delete_match

st.set_page_config(page_title="Settings | Wealth Tracker", page_icon="⚙️", layout="wide")
st.title("⚙️ Settings — Nominees")
render_sidebar()

st.caption(
    "Record nominee details per account / folio / policy. "
    "Multiple nominees allowed — percentages must total 100%."
)

_RELS = [
    "", "Spouse", "Son", "Daughter", "Father", "Mother",
    "Brother", "Sister", "Father-in-law", "Mother-in-law",
    "Son-in-law", "Daughter-in-law", "Grandson", "Granddaughter",
    "Nephew", "Niece", "Uncle", "Aunt", "Other",
]

# Common nominees — shown as dropdown; user can also type any name not in list
_NOMINEE_OPTS = ["", "Harsh Sharma", "Anusha Sharma", "Vinay Sharma", "Roopesh Sharma"]

# Auto-fill relationship when nominee is selected (owner → nominee → relationship)
_REL_LOOKUP: dict[tuple[str, str], str] = {
    ("Vinay",  "Harsh Sharma"):   "Spouse",
    ("Vinay",  "Anusha Sharma"):  "Daughter",
    ("Harsh",  "Vinay Sharma"):   "Spouse",
    ("Harsh",  "Anusha Sharma"):  "Daughter",
    ("Anusha", "Vinay Sharma"):   "Father",
    ("Anusha", "Harsh Sharma"):   "Mother",
    ("Mom",    "Vinay Sharma"):   "Son",
    ("Mom",    "Roopesh Sharma"): "Son",
}

_ALL_OWNERS    = ["Vinay", "Harsh", "Anusha", "Mom"]
_FAMILY_OWNERS = ["Vinay", "Harsh", "Anusha"]

# ── DB helpers ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def _load_nominees() -> list[dict]:
    return fetch("cfg_nominees")


def _nominees_for(asset_type: str, asset_ref: str) -> list[dict]:
    return [r for r in _load_nominees()
            if r.get("asset_type") == asset_type and r.get("asset_ref") == asset_ref]


def _save_asset(asset_type: str, asset_ref: str, owner: str, label: str, rows: list[dict]):
    service_delete_match("cfg_nominees", {"asset_type": asset_type, "asset_ref": asset_ref})
    for row in rows:
        service_insert("cfg_nominees", {
            "asset_type":            asset_type,
            "asset_ref":             asset_ref,
            "owner":                 owner,
            "label":                 label,
            "nominee_name":          str(row["Nominee"]),
            "relationship":          str(row.get("Relationship") or ""),
            "share_pct":             float(row.get("%") or 0),
            "nomination_registered": bool(row.get("Registered", False)),
            "notes":                 str(row.get("Notes") or ""),
        })
    st.cache_data.clear()


def _validate_and_save(rows_to_save, asset_type, asset_ref, owner, label, editor_key, fkey=None):
    _save_asset(asset_type, asset_ref, owner, label, rows_to_save)
    if fkey:
        st.session_state.pop(fkey, None)
    st.success("✅ Saved.")
    st.rerun()


# ── Per-asset editor ──────────────────────────────────────────────────────────

def _asset_editor(asset_type: str, asset_ref: str, owner: str, label: str, editor_key: str):
    existing = _nominees_for(asset_type, asset_ref)

    base_data = [{
        "Nominee":      r.get("nominee_name", ""),
        "%":            int(r.get("share_pct", 100)),
        "Relationship": r.get("relationship", ""),
        "Registered":   bool(r.get("nomination_registered", False)),
        "Notes":        r.get("notes", ""),
    } for r in existing] if existing else [
        {"Nominee": "", "%": 100, "Relationship": "", "Registered": False, "Notes": ""}
    ]

    tcol, _ = st.columns([1, 5])
    use_form = tcol.toggle("Form view", key=f"fv_{editor_key}")

    # ── Table view ────────────────────────────────────────────────────────────
    if not use_form:
        edited = st.data_editor(
            pd.DataFrame(base_data),
            column_config={
                "Nominee":      st.column_config.SelectboxColumn("Nominee",       options=_NOMINEE_OPTS, width="medium"),
                "%":            st.column_config.NumberColumn("%",                min_value=0, max_value=100, step=1, width="small"),
                "Relationship": st.column_config.SelectboxColumn("Relationship",  options=_RELS, width="medium"),
                "Registered":   st.column_config.CheckboxColumn("Registered",     width="medium"),
                "Notes":        st.column_config.TextColumn("Notes",              width="large"),
            },
            num_rows="dynamic",
            hide_index=True,
            use_container_width=True,
            key=editor_key,
        )

        needs_rerun = False
        for i, row in edited.iterrows():
            name = str(row.get("Nominee") or "").strip()
            rel  = str(row.get("Relationship") or "").strip()
            if name and not rel:
                auto_rel = _REL_LOOKUP.get((owner, name), "")
                if auto_rel:
                    es = st.session_state.get(editor_key, {})
                    er = es.get("edited_rows", {})
                    rd = er.get(i, {})
                    rd["Relationship"] = auto_rel
                    er[i] = rd
                    es["edited_rows"] = er
                    st.session_state[editor_key] = es
                    needs_rerun = True
        if needs_rerun:
            st.rerun()

        filled = edited[edited["Nominee"].notna() & (edited["Nominee"].astype(str).str.strip() != "")]
        if len(filled) > 0:
            total = filled["%"].sum()
            if total != 100:
                st.warning(f"⚠️ % sums to {int(total)}% — must total 100%")
            else:
                st.caption("✅ 100%")
        else:
            st.caption("⚠️ No nominee set")

        if st.button("💾 Save", key=f"sv_{editor_key}", type="primary"):
            rows_to_save = []
            for _, row in edited.iterrows():
                name = str(row.get("Nominee") or "").strip()
                if not name:
                    continue
                rel = str(row.get("Relationship") or "").strip() or _REL_LOOKUP.get((owner, name), "")
                rows_to_save.append({"Nominee": name, "%": row["%"], "Relationship": rel,
                                     "Registered": row["Registered"], "Notes": row["Notes"]})
            _validate_and_save(rows_to_save, asset_type, asset_ref, owner, label, editor_key)

    # ── Form view ─────────────────────────────────────────────────────────────
    else:
        fkey = f"fd_{editor_key}"
        if fkey not in st.session_state:
            st.session_state[fkey] = [dict(r) for r in base_data]

        rows = st.session_state[fkey]
        to_delete = []

        for i, row in enumerate(rows):
            r1 = st.columns([4, 1.5, 1.5, 0.6])
            nom_idx = _NOMINEE_OPTS.index(row["Nominee"]) if row["Nominee"] in _NOMINEE_OPTS else 0
            row["Nominee"]    = r1[0].selectbox("Nominee", _NOMINEE_OPTS, index=nom_idx,
                                                key=f"{editor_key}_fn_{i}")
            row["%"]          = r1[1].number_input("Share %", 0, 100, value=int(row["%"]),
                                                   key=f"{editor_key}_fp_{i}")
            row["Registered"] = r1[2].checkbox("Reg. done?", value=bool(row["Registered"]),
                                               key=f"{editor_key}_fc_{i}")
            if r1[3].button("🗑", key=f"{editor_key}_fdel_{i}", help="Remove"):
                to_delete.append(i)

            r2 = st.columns([3, 5])
            rel_idx = _RELS.index(row["Relationship"]) if row["Relationship"] in _RELS else 0
            row["Relationship"] = r2[0].selectbox("Relationship", _RELS, index=rel_idx,
                                                   key=f"{editor_key}_fr_{i}")
            row["Notes"]        = r2[1].text_input("Notes", value=str(row["Notes"] or ""),
                                                    key=f"{editor_key}_fnotes_{i}")
            if i < len(rows) - 1:
                st.divider()

        # Auto-fill relationship in form view
        needs_rerun = False
        for i, row in enumerate(rows):
            if str(row.get("Nominee") or "").strip() and not str(row.get("Relationship") or "").strip():
                auto_rel = _REL_LOOKUP.get((owner, row["Nominee"]), "")
                if auto_rel:
                    st.session_state[fkey][i]["Relationship"] = auto_rel
                    needs_rerun = True

        if to_delete:
            st.session_state[fkey] = [r for j, r in enumerate(rows) if j not in to_delete]
            needs_rerun = True

        if needs_rerun:
            st.rerun()

        if st.button("➕ Add nominee", key=f"{editor_key}_fadd"):
            st.session_state[fkey].append({"Nominee": "", "%": 0, "Relationship": "", "Registered": False, "Notes": ""})
            st.rerun()

        filled = [r for r in rows if str(r.get("Nominee") or "").strip()]
        if filled:
            total = sum(r.get("%", 0) for r in filled)
            if total != 100:
                st.warning(f"⚠️ % sums to {int(total)}% — must total 100%")
            else:
                st.caption("✅ 100%")
        else:
            st.caption("⚠️ No nominee set")

        if st.button("💾 Save", key=f"sv_{editor_key}", type="primary"):
            rows_to_save = []
            for row in rows:
                name = str(row.get("Nominee") or "").strip()
                if not name:
                    continue
                rel = str(row.get("Relationship") or "").strip() or _REL_LOOKUP.get((owner, name), "")
                rows_to_save.append({"Nominee": name, "%": row["%"], "Relationship": rel,
                                     "Registered": row["Registered"], "Notes": row["Notes"]})
            _validate_and_save(rows_to_save, asset_type, asset_ref, owner, label, editor_key, fkey)


# ── Per-owner page ────────────────────────────────────────────────────────────

def _owner_page(owner: str):
    is_family = owner in _FAMILY_OWNERS

    # Demat
    with st.expander("📈 Demat Account — India Equity", expanded=True):
        st.caption("Nomination is at the demat account level, not per stock.")
        _asset_editor("india_eq", owner, owner, f"{owner}'s Demat Account", f"{owner}_demat")

    # International Equity
    if is_family:
        with st.expander("🌍 International Equity — Broker Account", expanded=True):
            st.caption("Nomination is at the broker account level.")
            _asset_editor("intl_eq", owner, owner, f"{owner}'s International Broker", f"{owner}_intl")

    # Mutual Funds
    folio_map: dict[str, list[str]] = {}
    for h in fetch("cfg_mutual_funds"):
        if h.get("owner") != owner:
            continue
        raw_isin = h.get("isin", "")
        parts    = raw_isin.rsplit("_", 1)
        folio    = parts[0] if len(parts) == 2 else raw_isin
        folio_map.setdefault(folio, []).append(h.get("fund_name", raw_isin))

    if folio_map:
        with st.expander(f"📊 Mutual Funds — {len(folio_map)} Folio{'s' if len(folio_map) != 1 else ''}", expanded=True):
            st.caption("Nomination is at folio level.")
            for idx, (folio, schemes) in enumerate(sorted(folio_map.items())):
                st.markdown(f"**Folio {folio}** — {', '.join(sorted(set(schemes)))}")
                _asset_editor("mf", f"{owner}_{folio}", owner, f"{owner} — Folio {folio}", f"{owner}_mf_{idx}")
                st.divider()

    # Bank India
    banks_in = [b for b in fetch("cfg_bank_india") if b.get("owner", "Vinay") == owner]
    if banks_in:
        with st.expander(f"🏦 Bank Accounts India — {len(banks_in)} Account{'s' if len(banks_in) != 1 else ''}", expanded=True):
            for idx, b in enumerate(banks_in):
                bname = b.get("bank_name", "")
                acc   = b.get("account_no_last4", "")
                st.markdown(f"**{bname}** …{acc}")
                _asset_editor("bank_india", f"{owner}|{bname}|{acc}", owner,
                              f"{owner} — {bname} …{acc}", f"{owner}_bankin_{idx}")
                st.divider()

    # Bank UAE
    if is_family:
        banks_uae = [b for b in fetch("cfg_bank_uae") if b.get("owner", "Vinay") == owner]
        if banks_uae:
            with st.expander(f"🏦 Bank Accounts UAE — {len(banks_uae)} Account{'s' if len(banks_uae) != 1 else ''}", expanded=True):
                for idx, b in enumerate(banks_uae):
                    bname = b.get("bank_name", "")
                    acc   = b.get("account_no", "")
                    st.markdown(f"**{bname}** {acc}")
                    _asset_editor("bank_uae", f"{owner}|{bname}|{acc}", owner,
                                  f"{owner} — {bname} {acc}", f"{owner}_bankuae_{idx}")
                    st.divider()

    # Fixed Deposits
    fds = [fd for fd in fetch("cfg_fixed_deposits") if fd.get("owner", "Vinay") == owner]
    if fds:
        with st.expander(f"🏛 Fixed Deposits — {len(fds)}", expanded=True):
            for idx, fd in enumerate(fds):
                bank  = fd.get("bank", "")
                fd_no = fd.get("fd_no", "")
                st.markdown(f"**{bank}** FD {fd_no}")
                _asset_editor("fd", f"{owner}|{bank}|{fd_no}", owner,
                              f"{owner} — {bank} FD {fd_no}", f"{owner}_fd_{idx}")
                st.divider()

    # Insurance
    if is_family:
        policies = [p for p in fetch("cfg_insurance") if p.get("owner", "Vinay") == owner]
        if policies:
            with st.expander(f"🛡 Insurance — {len(policies)} Polic{'ies' if len(policies) != 1 else 'y'}", expanded=True):
                for idx, p in enumerate(policies):
                    company   = p.get("company_name", "")
                    policy_no = p.get("policy_no", "")
                    st.markdown(f"**{company}** {policy_no}")
                    _asset_editor("insurance", f"{owner}|{policy_no}", owner,
                                  f"{owner} — {company} {policy_no}", f"{owner}_ins_{idx}")
                    st.divider()


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_vinay, tab_harsh, tab_anusha, tab_mom = st.tabs(["👤 Vinay", "👤 Harsh", "👤 Anusha", "👩 Mom"])

with tab_vinay:  _owner_page("Vinay")
with tab_harsh:  _owner_page("Harsh")
with tab_anusha: _owner_page("Anusha")
with tab_mom:    _owner_page("Mom")
