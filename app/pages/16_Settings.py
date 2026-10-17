"""Settings — Nominee information for all asset classes."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd

from utils.sidebar import render_sidebar
from utils.db      import fetch, service_insert, service_delete

st.set_page_config(page_title="Settings | Wealth Tracker", page_icon="⚙️", layout="wide")
st.title("⚙️ Settings — Nominees")
render_sidebar()

st.caption(
    "Record nominee details for each asset. "
    "Nomination is at the account/folio/policy level — not per individual holding."
)

_RELS          = ["", "Spouse", "Child", "Parent", "Sibling", "Other"]
_ALL_OWNERS    = ["Vinay", "Harsh", "Anusha", "Mom"]
_FAMILY_OWNERS = ["Vinay", "Harsh", "Anusha"]

# ── DB helpers ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def _load_nominees_all() -> list[dict]:
    return fetch("cfg_nominees")


def _nominees_for(asset_type: str) -> dict:
    """Returns {asset_ref: row} for the given asset_type."""
    return {r["asset_ref"]: r for r in _load_nominees_all() if r.get("asset_type") == asset_type}


def _save(asset_type: str, rows: list[dict]):
    """Replace all nominee records for this asset_type."""
    service_delete("cfg_nominees", "asset_type", [asset_type])
    for row in rows:
        service_insert("cfg_nominees", row)
    st.cache_data.clear()


# ── Generic section renderer ──────────────────────────────────────────────────

def _section(asset_type: str, tab_key: str, base_rows: list[dict], readonly_cols: list[str]):
    """
    base_rows: list of dicts.
      Required key: 'asset_ref' (unique within asset_type).
      Optional keys: '_owner', '_label' (stored but not shown in table).
      All other keys become columns in the table.
    readonly_cols: column names that are shown but not editable.
    """
    nom = _nominees_for(asset_type)
    missing = sum(1 for ref in [r["asset_ref"] for r in base_rows]
                  if not nom.get(ref, {}).get("nominee_name", "").strip())
    if missing:
        st.warning(f"⚠️ {missing} row(s) have no nominee recorded.")
    elif base_rows:
        st.success("✅ All entries have a nominee recorded.")

    rows_internal = []   # keeps asset_ref + internal fields
    display_rows  = []   # what goes into data_editor

    for br in base_rows:
        ref   = br["asset_ref"]
        saved = nom.get(ref, {})
        internal = {"_ref": ref, "_owner": br.get("_owner", ""), "_label": br.get("_label", "")}
        row = {c: br.get(c, "") for c in readonly_cols}
        row["Nominee"]      = saved.get("nominee_name", "")
        row["Relationship"] = saved.get("relationship", "")
        row["Registered?"]  = saved.get("nomination_registered", False)
        row["Notes"]        = saved.get("notes", "")
        rows_internal.append(internal)
        display_rows.append(row)

    if not display_rows:
        st.info("No entries found.")
        return

    df = pd.DataFrame(display_rows)
    edited = st.data_editor(
        df,
        column_config={
            **{c: st.column_config.TextColumn(c, disabled=True) for c in readonly_cols},
            "Nominee":      st.column_config.TextColumn("Nominee",      width="medium"),
            "Relationship": st.column_config.SelectboxColumn("Relationship", options=_RELS, width="small"),
            "Registered?":  st.column_config.CheckboxColumn("Registered?",   width="small"),
            "Notes":        st.column_config.TextColumn("Notes",        width="large"),
        },
        disabled=readonly_cols,
        hide_index=True,
        use_container_width=True,
        key=f"ne_{tab_key}",
    )

    if st.button("💾 Save", key=f"sv_{tab_key}", type="primary"):
        to_save = []
        for i, internal in enumerate(rows_internal):
            to_save.append({
                "asset_type":            asset_type,
                "asset_ref":             internal["_ref"],
                "owner":                 internal["_owner"],
                "label":                 internal["_label"],
                "nominee_name":          str(edited.iloc[i].get("Nominee", "")      or ""),
                "relationship":          str(edited.iloc[i].get("Relationship", "") or ""),
                "nomination_registered": bool(edited.iloc[i].get("Registered?", False)),
                "notes":                 str(edited.iloc[i].get("Notes", "")        or ""),
            })
        _save(asset_type, to_save)
        st.success("✅ Saved.")
        st.rerun()


# ── Tabs ──────────────────────────────────────────────────────────────────────

(tab_demat, tab_intl, tab_mf,
 tab_bank_in, tab_bank_uae, tab_fd, tab_ins) = st.tabs([
    "📈 Demat (India Eq)",
    "🌍 International Eq",
    "📊 Mutual Funds",
    "🏦 Bank India",
    "🏦 Bank UAE",
    "🏛 Fixed Deposits",
    "🛡 Insurance",
])


# ── Demat accounts — one row per owner ───────────────────────────────────────
with tab_demat:
    st.caption("Nomination is registered at the demat account level, not per stock.")
    base = []
    for owner in _ALL_OWNERS:
        base.append({
            "asset_ref": owner,
            "_owner":    owner,
            "_label":    f"{owner}'s Demat Account",
            "Owner":     owner,
        })
    _section("india_eq", "demat", base, readonly_cols=["Owner"])


# ── International equity — one row per owner (no Mom) ────────────────────────
with tab_intl:
    st.caption("Nomination is registered at the broker account level.")
    base = []
    for owner in _FAMILY_OWNERS:
        base.append({
            "asset_ref": owner,
            "_owner":    owner,
            "_label":    f"{owner}'s International Broker Account",
            "Owner":     owner,
        })
    _section("intl_eq", "intl", base, readonly_cols=["Owner"])


# ── Mutual Funds — one row per owner + folio ─────────────────────────────────
with tab_mf:
    st.caption("Nomination is at folio level. One folio can hold multiple schemes.")
    all_mf = fetch("cfg_mutual_funds")

    # Group by (owner, folio_no)
    folio_map: dict[tuple, list[str]] = {}
    for h in all_mf:
        raw_isin = h.get("isin", "")
        parts    = raw_isin.rsplit("_", 1)
        folio    = parts[0] if len(parts) == 2 else raw_isin
        owner    = h.get("owner", "Vinay")
        key      = (owner, folio)
        folio_map.setdefault(key, []).append(h.get("fund_name", raw_isin))

    base = []
    for (owner, folio), schemes in sorted(folio_map.items()):
        base.append({
            "asset_ref":  f"{owner}_{folio}",
            "_owner":     owner,
            "_label":     f"{owner} — Folio {folio}",
            "Owner":      owner,
            "Folio No":   folio,
            "Schemes":    ", ".join(sorted(set(schemes))),
        })
    _section("mf", "mf", base, readonly_cols=["Owner", "Folio No", "Schemes"])


# ── Bank India — one row per account ─────────────────────────────────────────
with tab_bank_in:
    base = []
    for b in fetch("cfg_bank_india"):
        owner  = b.get("owner", "Vinay")
        bname  = b.get("bank_name", "")
        acc    = b.get("account_no_last4", "")
        ref    = f"{owner}|{bname}|{acc}"
        label  = f"{owner} — {bname} ...{acc}"
        base.append({
            "asset_ref":   ref,
            "_owner":      owner,
            "_label":      label,
            "Owner":       owner,
            "Bank":        bname,
            "Account No.": acc,
        })
    _section("bank_india", "bank_in", base, readonly_cols=["Owner", "Bank", "Account No."])


# ── Bank UAE — one row per account ───────────────────────────────────────────
with tab_bank_uae:
    base = []
    for b in fetch("cfg_bank_uae"):
        owner = b.get("owner", "Vinay")
        bname = b.get("bank_name", "")
        acc   = b.get("account_no", "")
        ref   = f"{owner}|{bname}|{acc}"
        label = f"{owner} — {bname} {acc}"
        base.append({
            "asset_ref":   ref,
            "_owner":      owner,
            "_label":      label,
            "Owner":       owner,
            "Bank":        bname,
            "Account No.": acc,
        })
    _section("bank_uae", "bank_uae", base, readonly_cols=["Owner", "Bank", "Account No."])


# ── Fixed Deposits — one row per FD ─────────────────────────────────────────
with tab_fd:
    base = []
    for fd in fetch("cfg_fixed_deposits"):
        owner = fd.get("owner", "Vinay")
        bank  = fd.get("bank", "")
        fd_no = fd.get("fd_no", "")
        ref   = f"{owner}|{bank}|{fd_no}"
        base.append({
            "asset_ref": ref,
            "_owner":    owner,
            "_label":    f"{owner} — {bank} FD {fd_no}",
            "Owner":     owner,
            "Bank":      bank,
            "FD No":     fd_no,
        })
    _section("fd", "fd", base, readonly_cols=["Owner", "Bank", "FD No"])


# ── Insurance — one row per policy ───────────────────────────────────────────
with tab_ins:
    base = []
    for p in fetch("cfg_insurance"):
        owner      = p.get("owner", "Vinay")
        company    = p.get("company_name", "")
        policy_no  = p.get("policy_no", "")
        ref        = f"{owner}|{policy_no}"
        base.append({
            "asset_ref": ref,
            "_owner":    owner,
            "_label":    f"{owner} — {company} {policy_no}",
            "Owner":     owner,
            "Company":   company,
            "Policy No": policy_no,
        })
    _section("insurance", "insurance", base, readonly_cols=["Owner", "Company", "Policy No"])
