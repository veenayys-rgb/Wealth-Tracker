"""Settings — Nominee information for all asset classes."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from utils.sidebar import render_sidebar
from utils.db      import fetch, service_insert, service_delete_match

st.set_page_config(page_title="Settings | Wealth Tracker", page_icon="⚙️", layout="wide")
st.title("⚙️ Settings — Nominees")
render_sidebar()

st.caption(
    "Record nominee details per account / folio / policy. "
    "Multiple nominees allowed for insurance — all others have one nominee at 100%."
)

_RELS = [
    "", "Spouse", "Son", "Daughter", "Father", "Mother",
    "Brother", "Sister", "Father-in-law", "Mother-in-law",
    "Son-in-law", "Daughter-in-law", "Grandson", "Granddaughter",
    "Nephew", "Niece", "Uncle", "Aunt", "Other",
]

_NOMINEE_OPTS = ["", "Harsh Sharma", "Anusha Sharma", "Vinay Sharma", "Roopesh Sharma"]

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

# Section header colours (background, foreground)
_CLR = {
    "demat":    ("#dbeafe", "#1e40af"),
    "intl":     ("#d1fae5", "#065f46"),
    "mf":       ("#dcfce7", "#15803d"),
    "bank_in":  ("#ffedd5", "#c2410c"),
    "bank_uae": ("#fef9c3", "#854d0e"),
    "fd":       ("#ede9fe", "#5b21b6"),
    "insurance":("#fee2e2", "#991b1b"),
}


# ── DB helpers ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def _load_nominees() -> list[dict]:
    return fetch("cfg_nominees")


def _nominees_for(asset_type: str, asset_ref: str) -> list[dict]:
    return [r for r in _load_nominees()
            if r.get("asset_type") == asset_type and r.get("asset_ref") == asset_ref]


def _nom_row(asset_type: str, asset_ref: str) -> dict:
    """Return nominee fields for a single-nominee asset (first row from DB or blank)."""
    rows = _nominees_for(asset_type, asset_ref)
    if rows:
        r = rows[0]
        return {
            "Nominee":      r.get("nominee_name", ""),
            "%":            int(r.get("share_pct", 100)),
            "Relationship": r.get("relationship", ""),
            "Registered":   bool(r.get("nomination_registered", False)),
            "Notes":        r.get("notes", ""),
        }
    return {"Nominee": "", "%": 100, "Relationship": "", "Registered": False, "Notes": ""}


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


# ── UI helpers ────────────────────────────────────────────────────────────────

def _section_hdr(title: str, color_key: str):
    bg, fg = _CLR[color_key]
    st.markdown(
        f'<div style="background:{bg};color:{fg};padding:7px 14px;'
        f'font-weight:600;font-size:14px;border-radius:6px;margin:12px 0 0 0;">'
        f'{title}</div>',
        unsafe_allow_html=True,
    )


def _col_cfg(id_col: str, id_width: str = "medium") -> dict:
    """Column config for single-nominee sections. id_col is the read-only identifier column."""
    return {
        id_col:         st.column_config.TextColumn(id_col, disabled=True, width=id_width),
        "Nominee":      st.column_config.SelectboxColumn("Nominee", options=_NOMINEE_OPTS, width="medium"),
        "%":            st.column_config.NumberColumn("%", min_value=0, max_value=100, step=1, width="small"),
        "Relationship": st.column_config.SelectboxColumn("Relationship", options=_RELS, width="medium"),
        "Registered":   st.column_config.CheckboxColumn("Reg", width="small"),
        "Notes":        st.column_config.TextColumn("Notes", width="large"),
    }


def _validate_single(edited: list[dict]):
    """Validation for single-nominee-per-row sections."""
    bad = [str(r.get("Nominee") or "").strip()
           for r in edited
           if str(r.get("Nominee") or "").strip() and int(r.get("%", 0)) != 100]
    if bad:
        st.warning(f"⚠️ These nominees have % ≠ 100: {', '.join(bad)}")
        return
    filled = sum(1 for r in edited if str(r.get("Nominee") or "").strip())
    if filled == 0:
        st.caption("⚠️ No nominees set")
    else:
        st.caption(f"✅ {filled}/{len(edited)} set")


def _save_section(edited: list[dict], asset_type: str, owner: str,
                  asset_refs: list[str], labels: list[str]):
    """Save all rows for a single-nominee section (one nominee per asset)."""
    for i, row in enumerate(edited):
        if i >= len(asset_refs):
            break
        name = str(row.get("Nominee") or "").strip()
        rel  = str(row.get("Relationship") or "").strip() or _REL_LOOKUP.get((owner, name), "")
        rows_to_save = [{
            "Nominee": name, "%": int(row.get("%", 100)), "Relationship": rel,
            "Registered": bool(row.get("Registered", False)),
            "Notes": str(row.get("Notes") or ""),
        }] if name else []
        _save_asset(asset_type, asset_refs[i], owner, labels[i], rows_to_save)


# ── Multi-nominee editor (insurance only) ─────────────────────────────────────

def _multi_nominee_editor(asset_type: str, asset_ref: str, owner: str,
                           label: str, editor_key: str):
    """Editable table for assets that allow multiple nominees (insurance)."""
    existing  = _nominees_for(asset_type, asset_ref)
    base_data = [{
        "Nominee":      r.get("nominee_name", ""),
        "%":            int(r.get("share_pct", 100)),
        "Relationship": r.get("relationship", ""),
        "Registered":   bool(r.get("nomination_registered", False)),
        "Notes":        r.get("notes", ""),
    } for r in existing] if existing else [
        {"Nominee": "", "%": 100, "Relationship": "", "Registered": False, "Notes": ""}
    ]

    edited = st.data_editor(
        base_data,
        column_config={
            "Nominee":      st.column_config.SelectboxColumn("Nominee", options=_NOMINEE_OPTS, width="medium"),
            "%":            st.column_config.NumberColumn("%", min_value=0, max_value=100, step=1, width="small"),
            "Relationship": st.column_config.SelectboxColumn("Relationship", options=_RELS, width="medium"),
            "Registered":   st.column_config.CheckboxColumn("Reg", width="small"),
            "Notes":        st.column_config.TextColumn("Notes", width="large"),
        },
        num_rows="dynamic",
        key=editor_key,
        use_container_width=True,
        hide_index=True,
    )

    filled = [r for r in edited if str(r.get("Nominee") or "").strip()]
    total  = sum(int(r.get("%", 0)) for r in filled)
    if not filled:
        st.caption("⚠️ No nominee set")
    elif total != 100:
        st.warning(f"⚠️ % sums to {int(total)}% — must total 100%")
    else:
        st.caption("✅ 100%")

    if st.button("💾 Save", key=f"sv_{editor_key}", type="primary"):
        rows_to_save = []
        for row in edited:
            name = str(row.get("Nominee") or "").strip()
            if not name:
                continue
            rel = str(row.get("Relationship") or "").strip() or _REL_LOOKUP.get((owner, name), "")
            rows_to_save.append({
                "Nominee": name, "%": int(row.get("%", 0)), "Relationship": rel,
                "Registered": bool(row.get("Registered", False)),
                "Notes": str(row.get("Notes") or ""),
            })
        _save_asset(asset_type, asset_ref, owner, label, rows_to_save)
        st.session_state.pop(editor_key, None)
        st.success("✅ Saved.")
        st.rerun()


# ── Per-owner page ────────────────────────────────────────────────────────────

def _owner_page(owner: str):
    is_family = owner in _FAMILY_OWNERS

    # ── 1. DEMAT ──────────────────────────────────────────────────────────────
    _section_hdr("📈 Demat Account — India Equity", "demat")
    st.caption("Nomination is at the demat account level, not per stock.")

    demat_data = [{"DP ID": "Demat Account", **_nom_row("india_eq", owner)}]
    edited_demat = st.data_editor(
        demat_data,
        column_config=_col_cfg("DP ID"),
        num_rows="fixed",
        key=f"{owner}_demat_de",
        use_container_width=True,
        hide_index=True,
    )
    _validate_single(edited_demat)
    if st.button("💾 Save", key=f"sv_{owner}_demat", type="primary"):
        _save_section(edited_demat, "india_eq", owner, [owner], [f"{owner}'s Demat Account"])
        st.session_state.pop(f"{owner}_demat_de", None)
        st.success("✅ Saved.")
        st.rerun()

    # ── 2. INTERNATIONAL EQUITY ───────────────────────────────────────────────
    if is_family:
        _section_hdr("🌍 International Equity — Broker Account", "intl")
        st.caption("Nomination is at the broker account level.")

        intl_data = [{"Account": "Broker Account", **_nom_row("intl_eq", owner)}]
        edited_intl = st.data_editor(
            intl_data,
            column_config=_col_cfg("Account"),
            num_rows="fixed",
            key=f"{owner}_intl_de",
            use_container_width=True,
            hide_index=True,
        )
        _validate_single(edited_intl)
        if st.button("💾 Save", key=f"sv_{owner}_intl", type="primary"):
            _save_section(edited_intl, "intl_eq", owner, [owner], [f"{owner}'s International Broker"])
            st.session_state.pop(f"{owner}_intl_de", None)
            st.success("✅ Saved.")
            st.rerun()

    # ── 3. MUTUAL FUNDS ───────────────────────────────────────────────────────
    folio_map: dict[str, list[str]] = {}
    for h in fetch("cfg_mutual_funds"):
        if h.get("owner") != owner:
            continue
        raw_isin = h.get("isin", "")
        parts    = raw_isin.rsplit("_", 1)
        folio    = parts[0] if len(parts) == 2 else raw_isin
        folio_map.setdefault(folio, []).append(h.get("fund_name", raw_isin))

    if folio_map:
        _section_hdr(
            f"📊 Mutual Funds — {len(folio_map)} Folio{'s' if len(folio_map) != 1 else ''}",
            "mf",
        )
        st.caption("Nomination is at folio level.")

        mf_refs, mf_labels, mf_data = [], [], []
        for folio, schemes in sorted(folio_map.items()):
            ref = f"{owner}_{folio}"
            mf_data.append({
                "Folio No": folio,
                "Schemes":  ", ".join(sorted(set(schemes))),
                **_nom_row("mf", ref),
            })
            mf_refs.append(ref)
            mf_labels.append(f"{owner} — Folio {folio}")

        edited_mf = st.data_editor(
            mf_data,
            column_config={
                "Folio No": st.column_config.TextColumn("Folio No", disabled=True, width="small"),
                "Schemes":  st.column_config.TextColumn("Schemes",  disabled=True, width="large"),
                "Nominee":      st.column_config.SelectboxColumn("Nominee", options=_NOMINEE_OPTS, width="medium"),
                "%":            st.column_config.NumberColumn("%", min_value=0, max_value=100, step=1, width="small"),
                "Relationship": st.column_config.SelectboxColumn("Relationship", options=_RELS, width="medium"),
                "Registered":   st.column_config.CheckboxColumn("Reg", width="small"),
                "Notes":        st.column_config.TextColumn("Notes", width="large"),
            },
            num_rows="fixed",
            key=f"{owner}_mf_de",
            use_container_width=True,
            hide_index=True,
        )
        _validate_single(edited_mf)
        if st.button("💾 Save", key=f"sv_{owner}_mf", type="primary"):
            _save_section(edited_mf, "mf", owner, mf_refs, mf_labels)
            st.session_state.pop(f"{owner}_mf_de", None)
            st.success("✅ Saved.")
            st.rerun()

    # ── 4. BANK ACCOUNTS INDIA ────────────────────────────────────────────────
    banks_in = [b for b in fetch("cfg_bank_india") if b.get("owner", "Vinay") == owner]
    if banks_in:
        _section_hdr(
            f"🏦 Bank Accounts India — {len(banks_in)} Account{'s' if len(banks_in) != 1 else ''}",
            "bank_in",
        )

        bi_refs, bi_labels, bi_data = [], [], []
        for b in banks_in:
            bname = b.get("bank_name", "")
            acc   = b.get("account_no_last4", "")
            ref   = f"{owner}|{bname}|{acc}"
            bi_data.append({"Account": f"{bname} …{acc}", **_nom_row("bank_india", ref)})
            bi_refs.append(ref)
            bi_labels.append(f"{owner} — {bname} …{acc}")

        edited_bi = st.data_editor(
            bi_data,
            column_config=_col_cfg("Account"),
            num_rows="fixed",
            key=f"{owner}_bankin_de",
            use_container_width=True,
            hide_index=True,
        )
        _validate_single(edited_bi)
        if st.button("💾 Save", key=f"sv_{owner}_bankin", type="primary"):
            _save_section(edited_bi, "bank_india", owner, bi_refs, bi_labels)
            st.session_state.pop(f"{owner}_bankin_de", None)
            st.success("✅ Saved.")
            st.rerun()

    # ── 5. BANK ACCOUNTS UAE ─────────────────────────────────────────────────
    if is_family:
        banks_uae = [b for b in fetch("cfg_bank_uae") if b.get("owner", "Vinay") == owner]
        if banks_uae:
            _section_hdr(
                f"🏦 Bank Accounts UAE — {len(banks_uae)} Account{'s' if len(banks_uae) != 1 else ''}",
                "bank_uae",
            )

            bu_refs, bu_labels, bu_data = [], [], []
            for b in banks_uae:
                bname = b.get("bank_name", "")
                acc   = b.get("account_no", "")
                ref   = f"{owner}|{bname}|{acc}"
                bu_data.append({"Account": f"{bname} {acc}", **_nom_row("bank_uae", ref)})
                bu_refs.append(ref)
                bu_labels.append(f"{owner} — {bname} {acc}")

            edited_bu = st.data_editor(
                bu_data,
                column_config=_col_cfg("Account"),
                num_rows="fixed",
                key=f"{owner}_bankuae_de",
                use_container_width=True,
                hide_index=True,
            )
            _validate_single(edited_bu)
            if st.button("💾 Save", key=f"sv_{owner}_bankuae", type="primary"):
                _save_section(edited_bu, "bank_uae", owner, bu_refs, bu_labels)
                st.session_state.pop(f"{owner}_bankuae_de", None)
                st.success("✅ Saved.")
                st.rerun()

    # ── 6. FIXED DEPOSITS ─────────────────────────────────────────────────────
    fds = [fd for fd in fetch("cfg_fixed_deposits") if fd.get("owner", "Vinay") == owner]
    if fds:
        _section_hdr(f"🏛 Fixed Deposits — {len(fds)}", "fd")

        fd_refs, fd_labels, fd_data = [], [], []
        for fd in fds:
            bank  = fd.get("bank", "")
            fd_no = fd.get("fd_no", "")
            ref   = f"{owner}|{bank}|{fd_no}"
            fd_data.append({"FD / Bank": f"{bank}  {fd_no}", **_nom_row("fd", ref)})
            fd_refs.append(ref)
            fd_labels.append(f"{owner} — {bank} FD {fd_no}")

        edited_fd = st.data_editor(
            fd_data,
            column_config={
                "FD / Bank":    st.column_config.TextColumn("FD / Bank", disabled=True, width="medium"),
                "Nominee":      st.column_config.SelectboxColumn("Nominee", options=_NOMINEE_OPTS, width="medium"),
                "%":            st.column_config.NumberColumn("%", min_value=0, max_value=100, step=1, width="small"),
                "Relationship": st.column_config.SelectboxColumn("Relationship", options=_RELS, width="medium"),
                "Registered":   st.column_config.CheckboxColumn("Reg", width="small"),
                "Notes":        st.column_config.TextColumn("Notes", width="large"),
            },
            num_rows="fixed",
            key=f"{owner}_fd_de",
            use_container_width=True,
            hide_index=True,
        )
        _validate_single(edited_fd)
        if st.button("💾 Save", key=f"sv_{owner}_fd", type="primary"):
            _save_section(edited_fd, "fd", owner, fd_refs, fd_labels)
            st.session_state.pop(f"{owner}_fd_de", None)
            st.success("✅ Saved.")
            st.rerun()

    # ── 7. INSURANCE (multi-nominee per policy) ───────────────────────────────
    if is_family:
        policies = [p for p in fetch("cfg_insurance") if p.get("owner", "Vinay") == owner]
        if policies:
            _section_hdr(
                f"🛡 Insurance — {len(policies)} Polic{'ies' if len(policies) != 1 else 'y'}",
                "insurance",
            )
            st.caption("Multiple nominees allowed — % per policy must total 100%.")
            for idx, p in enumerate(policies):
                company   = p.get("company_name", "")
                policy_no = p.get("policy_no", "")
                ref       = f"{owner}|{policy_no}"
                label     = f"{owner} — {company} {policy_no}"
                st.markdown(f"**{company} — Policy {policy_no}**")
                _multi_nominee_editor("insurance", ref, owner, label, f"{owner}_ins_{idx}")
                if idx < len(policies) - 1:
                    st.divider()


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_vinay, tab_harsh, tab_anusha, tab_mom = st.tabs(["👤 Vinay", "👤 Harsh", "👤 Anusha", "👩 Mom"])

with tab_vinay:  _owner_page("Vinay")
with tab_harsh:  _owner_page("Harsh")
with tab_anusha: _owner_page("Anusha")
with tab_mom:    _owner_page("Mom")
