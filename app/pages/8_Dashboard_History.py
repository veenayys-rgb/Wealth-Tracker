"""Dashboard History — manual portfolio snapshots across all categories."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd

from utils.sidebar import render_sidebar
from utils.db      import fetch, get_forex, service_insert, service_delete
from utils.fmt     import ind_num, utc_to_ist

st.set_page_config(page_title="Dashboard History | Wealth Tracker", page_icon="📸", layout="wide")
st.title("📸 Dashboard History")
render_sidebar()

_OWNERS = ["Vinay", "Harsh", "Anusha", "Mom"]
_FAMILY = ["Vinay", "Harsh", "Anusha"]
_CATS   = ["india_eq", "mf", "intl_eq", "bank_india", "bank_uae", "fd", "insurance"]
_CAT_LABELS = {
    "india_eq":   "India Equity",
    "mf":         "Mutual Funds",
    "intl_eq":    "Intl Equity",
    "bank_india": "Bank India",
    "bank_uae":   "Bank UAE",
    "fd":         "Fixed Deposits",
    "insurance":  "Insurance",
}


def _fx(forex: dict, currency: str) -> float:
    if currency == "AED": return forex.get("AED_INR", 0.0)
    if currency == "USD": return forex.get("USD_INR", 0.0)
    return 1.0


def _compute_snapshot() -> dict:
    """Load live holdings + prices and return a flat dict of per-owner per-category values."""
    forex       = get_forex()
    eq_prices   = {r["symbol"]: float(r["price"]) for r in fetch("equity_india_prices")         if r.get("price")}
    mf_navs     = {r["isin"]:   float(r["nav"])   for r in fetch("mf_navs")                     if r.get("nav")}
    intl_prices = {r["symbol"]: float(r["price"]) for r in fetch("equity_international_prices") if r.get("price")}

    all_india_eq = fetch("cfg_equity_india")
    all_intl_eq  = fetch("cfg_equity_international")
    all_mf       = fetch("cfg_mutual_funds")
    all_bank_in  = fetch("cfg_bank_india")
    all_bank_uae = fetch("cfg_bank_uae")
    all_fd       = fetch("cfg_fixed_deposits")
    all_ins      = fetch("cfg_insurance")

    snap = {}
    for owner in _OWNERS:
        p = owner.lower()

        # India Equity
        ie = 0.0
        for h in all_india_eq:
            if h.get("owner") != owner:
                continue
            price = eq_prices.get(h.get("symbol", "").upper(), 0)
            qty   = float(h.get("qty", 0))
            ie   += qty * price if price else qty * float(h.get("avg_cost", 0))
        snap[f"{p}_india_eq"] = ie

        # Mutual Funds
        mf = 0.0
        for h in all_mf:
            if h.get("owner") != owner:
                continue
            nav   = mf_navs.get(h.get("isin", "").upper(), 0)
            units = float(h.get("units", 0))
            mf   += units * nav if nav else units * float(h.get("avg_nav", 0))
        snap[f"{p}_mf"] = mf

        # International Equity (Mom has no intl holdings)
        intl = 0.0
        if owner != "Mom":
            for h in all_intl_eq:
                if h.get("owner") != owner:
                    continue
                price = intl_prices.get(h.get("symbol", "").upper(), 0)
                curr  = h.get("currency", "AED")
                qty   = float(h.get("qty", 0))
                intl += qty * price * _fx(forex, curr) if price else qty * float(h.get("avg_cost", 0)) * _fx(forex, curr)
        snap[f"{p}_intl_eq"] = intl

        # Bank India (INR)
        bank_in = 0.0
        for b in all_bank_in:
            if b.get("owner", "Vinay") != owner:
                continue
            bank_in += float(b.get("balance", 0))
        snap[f"{p}_bank_india"] = bank_in

        # Bank UAE (converted to INR; Mom has no UAE account)
        bank_uae = 0.0
        if owner != "Mom":
            for b in all_bank_uae:
                if b.get("owner", "Vinay") != owner:
                    continue
                bank_uae += float(b.get("balance_aed", 0)) * _fx(forex, b.get("currency", "AED"))
        snap[f"{p}_bank_uae"] = bank_uae

        # Fixed Deposits
        fd = 0.0
        for r in all_fd:
            if r.get("owner", "Vinay") != owner:
                continue
            fd += float(r.get("amount", 0)) * _fx(forex, r.get("currency", "INR"))
        snap[f"{p}_fd"] = fd

        # Insurance (Mom has no insurance entries in TABLE_MAP)
        ins = 0.0
        if owner != "Mom":
            for r in all_ins:
                if r.get("owner", "Vinay") != owner:
                    continue
                ins += float(r.get("surrender_value", 0)) * _fx(forex, r.get("currency", "INR"))
        snap[f"{p}_insurance"] = ins

    return snap


def _cat_sum(snap: dict, owners: list, cat: str) -> float:
    return sum(float(snap.get(f"{o.lower()}_{cat}", 0)) for o in owners)


def _grand_total(snap: dict, owners: list) -> float:
    return sum(_cat_sum(snap, owners, c) for c in _CATS)


def _fmt_ts(ts: str) -> str:
    return utc_to_ist(ts).replace(" IST", "")


# ── Record Snapshot button ────────────────────────────────────────────────────

btn_col, _ = st.columns([1, 5])
with btn_col:
    if st.button("📸 Record Snapshot", type="primary", use_container_width=True):
        with st.spinner("Computing portfolio snapshot…"):
            try:
                service_insert("dashboard_snapshots", _compute_snapshot())
                st.success("✅ Snapshot recorded.")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to record snapshot: {exc}")


# ── Load snapshots ────────────────────────────────────────────────────────────

_snaps = sorted(fetch("dashboard_snapshots"), key=lambda r: r["recorded_at"])


# ── Tile renderer ─────────────────────────────────────────────────────────────

def _render_tiles(owners: list):
    if not _snaps:
        st.info("No snapshots recorded yet.")
        return
    latest = _snaps[-1]
    prev   = _snaps[-2] if len(_snaps) >= 2 else None

    cols = st.columns(len(_CATS))
    for i, cat in enumerate(_CATS):
        val   = _cat_sum(latest, owners, cat)
        d_val = _cat_sum(latest, owners, cat) - _cat_sum(prev, owners, cat) if prev else None
        delta_html = ""
        if d_val is not None and abs(d_val) > 0:
            color = "green" if d_val >= 0 else "red"
            sign  = "+" if d_val >= 0 else ""
            delta_html = (f'<div style="font-size:0.72rem;color:{color};margin-top:2px">'
                          f'{sign}{ind_num(d_val, decimals=0)}</div>')
        cols[i].markdown(
            f'<div style="font-size:0.72rem;color:gray;font-weight:500;margin-bottom:2px">'
            f'{_CAT_LABELS[cat]}</div>'
            f'<div style="font-size:0.95rem;font-weight:600">{ind_num(val, decimals=0)}</div>'
            f'{delta_html}',
            unsafe_allow_html=True,
        )

    total   = _grand_total(latest, owners)
    d_total = total - _grand_total(prev, owners) if prev else None
    delta_html = ""
    if d_total is not None and abs(d_total) > 0:
        color = "green" if d_total >= 0 else "red"
        sign  = "+" if d_total >= 0 else ""
        delta_html = (f'<span style="font-size:0.85rem;color:{color};margin-left:10px">'
                      f'{sign}{ind_num(d_total, decimals=0)}</span>')
    st.markdown(
        f'<p style="margin-top:14px">'
        f'<span style="font-size:0.8rem;color:gray;font-weight:500">Grand Total &nbsp;</span>'
        f'<span style="font-size:1.25rem;font-weight:700">{ind_num(total)}</span>'
        f'{delta_html}</p>',
        unsafe_allow_html=True,
    )


# ── History table ─────────────────────────────────────────────────────────────

def _render_table(owners: list, tab_key: str):
    if not _snaps:
        return

    rows = []
    for i, s in enumerate(reversed(_snaps)):
        orig_i  = len(_snaps) - 1 - i
        prev_s  = _snaps[orig_i - 1] if orig_i > 0 else None
        total   = _grand_total(s, owners)
        d_total = total - _grand_total(prev_s, owners) if prev_s else None
        rows.append({
            "☑":         False,
            "Recorded":  _fmt_ts(s["recorded_at"]),
            **{_CAT_LABELS[c]: ind_num(_cat_sum(s, owners, c), decimals=0) for c in _CATS},
            "Total":     ind_num(total),
            "Δ vs prev": (("+" if d_total >= 0 else "") + ind_num(d_total, decimals=0)) if d_total is not None else "—",
            "_id":       s["id"],
        })

    display_df = pd.DataFrame([{k: v for k, v in r.items() if k != "_id"} for r in rows])
    edited = st.data_editor(
        display_df,
        column_config={"☑": st.column_config.CheckboxColumn("☑", width="small")},
        disabled=[c for c in display_df.columns if c != "☑"],
        hide_index=True,
        use_container_width=True,
        key=f"tbl_{tab_key}",
    )

    if st.button("🗑️ Delete Selected", key=f"del_{tab_key}"):
        sel = edited[edited["☑"]].index.tolist()
        if sel:
            service_delete("dashboard_snapshots", "id", [rows[i]["_id"] for i in sel])
            st.success(f"✅ {len(sel)} snapshot(s) deleted.")
            st.rerun()
        else:
            st.warning("Select at least one snapshot to delete.")


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_fam, tab_all, tab_vinay, tab_anusha, tab_harsh, tab_mom = st.tabs([
    "👨‍👩‍👦 Vinay Family", "🏠 All Members", "👤 Vinay", "👤 Anusha", "👤 Harsh", "👩 Mom",
])

_TAB_OWNERS = {
    "fam":    _FAMILY,
    "all":    _OWNERS,
    "vinay":  ["Vinay"],
    "anusha": ["Anusha"],
    "harsh":  ["Harsh"],
    "mom":    ["Mom"],
}

for _tab, _key in zip(
    [tab_fam, tab_all, tab_vinay, tab_anusha, tab_harsh, tab_mom],
    ["fam",   "all",   "vinay",   "anusha",   "harsh",   "mom"],
):
    with _tab:
        _render_tiles(_TAB_OWNERS[_key])
        st.divider()
        _render_table(_TAB_OWNERS[_key], _key)
