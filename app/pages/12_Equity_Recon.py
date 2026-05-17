"""Equity Recon — HDFC Demat holding statement reconciliation."""
import sys, os, re, io, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
import pdfplumber
import pandas as pd
from utils.config import load, save
from utils.fmt import ind_num

st.set_page_config(page_title="Equity Recon | Wealth Tracker", page_icon="📋", layout="wide")
st.title("📋 Equity Reconciliation — HDFC Demat")
st.caption("Upload an HDFC Depository Holding Statement PDF to compare with stored holdings.")
render_sidebar()

# ── DP Account → NRE/NRO mapping (stored in app/) ─────────────────────────────
_MAP_FILE = os.path.join(os.path.dirname(__file__), "..", "dp_account_map.json")

def _load_map() -> dict:
    if os.path.exists(_MAP_FILE):
        with open(_MAP_FILE) as f:
            return json.load(f)
    return {}

def _save_map(m: dict):
    with open(_MAP_FILE, "w") as f:
        json.dump(m, f, indent=2)

dp_map = _load_map()

with st.expander("⚙️ DP Account → NRE/NRO Mapping (one-time setup)", expanded=not dp_map):
    st.caption(
        "Each HDFC Demat PDF contains a **DP Account No** in its header. "
        "Enter the account numbers for your NRE and NRO demat accounts once — "
        "the tool will auto-detect the holding type on upload."
    )
    col_nre, col_nro = st.columns(2)
    existing_nre = next((k for k, v in dp_map.items() if v == "NRE"), "")
    existing_nro = next((k for k, v in dp_map.items() if v == "NRO"), "")
    inp_nre = col_nre.text_input("NRE DP Account No", value=existing_nre, placeholder="e.g. 67037164")
    inp_nro = col_nro.text_input("NRO DP Account No", value=existing_nro, placeholder="e.g. 58248915")
    if st.button("💾 Save Mapping"):
        new_map = {}
        if inp_nre.strip():
            new_map[inp_nre.strip()] = "NRE"
        if inp_nro.strip():
            new_map[inp_nro.strip()] = "NRO"
        _save_map(new_map)
        dp_map = new_map
        st.success("Mapping saved.")
        st.rerun()

# ── Regex ──────────────────────────────────────────────────────────────────────
ROW_RE = re.compile(
    r'^(IN[A-Z0-9]{10})\s+'
    r'(.+?)\s+'
    r'([\d,]+\.\d{3})\s+'
    r'([\d,]+\.\d{2})\s+'
    r'([\d,]+\.\d{2})\s+Free'
)
SKIP_RE = re.compile(
    r'HDFC Bank Depository|Holding Statement|Account Type|Page Number|'
    r'Market Rate Date|Total Valuation|Nomination Details|Authorised Signatory|'
    r'HDFC Bank Limited|Registered\s*:\s*Yes',
    re.IGNORECASE
)
INVESTOR_RE = re.compile(r'^([A-Z][A-Z ]+)$', re.MULTILINE)
ACCT_RE     = re.compile(r'DP Account No\s*[:\s]+(\d+)', re.IGNORECASE)


def extract_holdings(file_bytes: bytes) -> tuple[str, str, list[dict]]:
    """Return (investor_name, dp_account_no, holdings_list) from HDFC PDF bytes."""
    raw_pages, investor, dp_account = [], "", ""

    with pdfplumber.open(file_bytes) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            raw_pages.append(t)
            if not dp_account:
                m = ACCT_RE.search(t)
                if m:
                    dp_account = m.group(1).strip()

    full_text = "\n".join(raw_pages)

    # Detect investor name
    for line in full_text.splitlines()[:20]:
        line = line.strip()
        if INVESTOR_RE.match(line) and len(line.split()) >= 2 and "BANK" not in line:
            investor = line.title()
            break

    # Join continuation lines
    lines, joined = full_text.splitlines(), []
    for line in lines:
        line = line.strip()
        if not line or SKIP_RE.search(line):
            continue
        line = re.sub(r'^Free Balance\s+', '', line)
        if re.match(r'^IN[A-Z0-9]{10}\s', line):
            joined.append(line)
        elif joined:
            joined[-1] += " " + line

    records = []
    for line in joined:
        m = ROW_RE.match(line.strip())
        if not m:
            continue
        isin, desc, bal_str, rate_str, val_str = m.groups()
        qty   = float(bal_str.replace(",", ""))
        rate  = float(rate_str.replace(",", ""))
        value = float(val_str.replace(",", ""))
        records.append({
            "isin":  isin.upper(),
            "desc":  desc.strip(),
            "scrip": "ETF/MF" if isin.startswith("INF") else "EQ",
            "qty":   qty,
            "rate":  rate,
            "value": value,
        })

    return investor, dp_account, records


# ── UI ─────────────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
owner    = c1.selectbox("Owner", ["Vinay", "Harsh", "Anusha"])
uploaded = c3.file_uploader("HDFC PDF", type=["pdf", "PDF"])

if not uploaded:
    st.info("Upload an HDFC Depository Holding Statement PDF to begin.")
    st.stop()

# ── Parse ──────────────────────────────────────────────────────────────────────
try:
    investor, dp_account, hdfc = extract_holdings(io.BytesIO(uploaded.read()))
except Exception as e:
    st.error(f"Failed to parse PDF: {e}")
    st.stop()

# ── Auto-detect NRE/NRO ────────────────────────────────────────────────────────
auto_ht    = dp_map.get(dp_account, "")
ht_options = ["NRO", "NRE"]

if auto_ht:
    default_idx = ht_options.index(auto_ht)
    c2.success(f"Auto-detected: **{auto_ht}** (DP Acct: `{dp_account}`)")
else:
    default_idx = 0
    if dp_account:
        c2.warning(f"DP Acct `{dp_account}` not in mapping — please select manually or update config above.")
    else:
        c2.warning("DP Account No not found in PDF — please select manually.")

holding_type = c2.selectbox("Holding Type", ht_options, index=default_idx)

if not hdfc:
    st.error("No holdings found. Check the PDF format.")
    st.stop()

st.success(f"Parsed **{len(hdfc)} holdings** for **{investor or owner}** ({holding_type}).")

# ── Load stored data ───────────────────────────────────────────────────────────
fname_map = {"Vinay": "equity_india_vinay.json",
             "Harsh": "equity_india_harsh.json",
             "Anusha": "equity_india_anusha.json"}
stored         = load(fname_map[owner])
stored_ht      = [h for h in stored if h.get("holding_type", "").upper() == holding_type.upper()]
stored_by_isin = {h["isin"].upper(): h for h in stored_ht}

# ── MF ISIN classification ─────────────────────────────────────────────────────
# Rule: INF ISINs in the MF tracker → skip (reconcile via MF Recon)
#       INF ISINs NOT in MF tracker  → include (exchange-traded ETF, priced via yfinance)
mf_fname_map = {"Vinay": "mutual_funds_vinay.json",
                "Harsh": "mutual_funds_harsh.json",
                "Anusha": "mutual_funds_anusha.json"}
mf_stored = load(mf_fname_map[owner])
mf_isins  = {h["isin"].upper() for h in mf_stored if h.get("isin")}

etf_skipped = [r for r in hdfc if r["isin"] in mf_isins]
etf_equity  = [r for r in hdfc if r["scrip"] == "ETF/MF" and r["isin"] not in mf_isins]
if etf_skipped:
    names = ", ".join(f"{r['desc']} ({r['isin']})" for r in etf_skipped)
    st.info(
        f"ℹ️ {len(etf_skipped)} holding(s) found in both HDFC statement and MF tracker — "
        "excluded from equity comparison (reconcile via **MF Recon**):\n\n"
        f"{names}"
    )
if etf_equity:
    names = ", ".join(f"{r['desc']} ({r['isin']})" for r in etf_equity)
    st.info(
        f"ℹ️ {len(etf_equity)} exchange-traded ETF(s) with INF ISIN not in MF tracker — "
        "included in equity comparison below:\n\n"
        f"{names}"
    )

# ── Build comparison ───────────────────────────────────────────────────────────
rows = []
for rec in hdfc:
    if rec["isin"] in mf_isins:
        continue   # tracked via MF Recon — skip
    isin     = rec["isin"]
    s        = stored_by_isin.get(isin)
    s_qty    = float(s["qty"])      if s else None
    s_cost   = float(s["avg_cost"]) if s else None
    qty_diff = round(rec["qty"] - s_qty, 3) if s_qty is not None else None

    if s is None:
        status = "🆕 New"
    elif qty_diff is not None and abs(qty_diff) > 0.001:
        status = "⚠️ Qty differs"
    else:
        status = "✅ Match"

    rows.append({
        "Status":          status,
        "ISIN":            isin,
        "Description":     rec["desc"],
        "Type":            rec["scrip"],
        "HDFC Qty":        rec["qty"],
        "Stored Qty":      s_qty,
        "Qty Diff":        qty_diff,
        "HDFC Rate (₹)":   rec["rate"],
        "HDFC Value (₹)":  rec["value"],
        "Stored Avg Cost": s_cost,
    })

hdfc_isins = {r["isin"] for r in hdfc}
for h in stored_ht:
    if h["isin"].upper() not in hdfc_isins:
        rows.append({
            "Status":          "❌ Missing in HDFC",
            "ISIN":            h["isin"].upper(),
            "Description":     h.get("company_name", ""),
            "Type":            "EQ",
            "HDFC Qty":        None,
            "Stored Qty":      float(h["qty"]),
            "Qty Diff":        None,
            "HDFC Rate (₹)":   None,
            "HDFC Value (₹)":  None,
            "Stored Avg Cost": float(h["avg_cost"]),
        })

df = pd.DataFrame(rows)

# ── Summary ────────────────────────────────────────────────────────────────────
total_val = sum(r["value"] for r in hdfc if r["isin"] not in mf_isins)
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Holdings in HDFC",    len(hdfc))
c2.metric("✅ Match",             sum(1 for r in rows if r["Status"] == "✅ Match"))
c3.metric("⚠️ Qty differs",       sum(1 for r in rows if "differ" in r["Status"]))
c4.metric("🆕 New",               sum(1 for r in rows if r["Status"] == "🆕 New"))
c5.metric("❌ Missing in HDFC",   sum(1 for r in rows if "Missing" in r["Status"]))
c6.metric("HDFC Total Value",    ind_num(total_val))

st.divider()

# ── Comparison table ───────────────────────────────────────────────────────────
st.subheader("Comparison")
status_filter = st.multiselect(
    "Filter by status",
    options=df["Status"].unique().tolist(),
    default=df["Status"].unique().tolist(),
)
view = df[df["Status"].isin(status_filter)].copy()

fmt = {
    "HDFC Qty":        lambda v: f"{v:,.3f}"  if v is not None else "—",
    "Stored Qty":      lambda v: f"{v:,.3f}"  if v is not None else "—",
    "Qty Diff":        lambda v: f"{v:+,.3f}" if v is not None else "—",
    "HDFC Rate (₹)":   lambda v: ind_num(v)   if v is not None else "—",
    "HDFC Value (₹)":  lambda v: ind_num(v)   if v is not None else "—",
    "Stored Avg Cost": lambda v: ind_num(v)   if v is not None else "—",
}

def _colour(v):
    if not isinstance(v, str): return ""
    if v.startswith("+"): return "color:green"
    if v.startswith("-"): return "color:red"
    return ""

st.dataframe(
    view.style.format(fmt).map(_colour, subset=["Qty Diff"]),
    use_container_width=True,
    hide_index=True,
)

st.divider()

# ── Sync ───────────────────────────────────────────────────────────────────────
to_update = [r for r in rows if "differ" in r["Status"]]
to_add    = [r for r in rows if r["Status"] == "🆕 New"]
missing   = [r for r in rows if "Missing" in r["Status"]]

if missing:
    names = ", ".join(f"{r['Description']} ({r['ISIN']})" for r in missing)
    st.warning(f"⚠️ {len(missing)} holding(s) in tracker not found in HDFC statement — please review manually:\n\n{names}")

st.info("ℹ️ HDFC statement provides current price only — avg cost will not be updated. "
        "New stocks are added with avg cost = 0; please update via the India Equity page.")

can_sync = len(to_update) + len(to_add) > 0
if can_sync:
    st.info(f"Ready to sync: **{len(to_update)}** holding(s) to update qty  |  **{len(to_add)}** new holding(s) to add")

if st.button("🔄 Sync to Tracker", disabled=not can_sync, type="primary"):
    hdfc_by_isin = {r["isin"]: r for r in hdfc}

    # Update qty for differing holdings
    updated = 0
    for h in stored:
        if h.get("holding_type", "").upper() != holding_type.upper():
            continue
        hrec = hdfc_by_isin.get(h["isin"].upper())
        if hrec and abs(float(h["qty"]) - hrec["qty"]) > 0.001:
            h["qty"] = hrec["qty"]
            updated += 1

    # Add new holdings
    added, existing_isins = 0, {h["isin"].upper() for h in stored
                                  if h.get("holding_type", "").upper() == holding_type.upper()}
    for r in to_add:
        if r["ISIN"] not in existing_isins:
            stored.append({
                "isin":         r["ISIN"],
                "company_name": r["Description"],
                "symbol":       "",        # fill in via India Equity page for price fetching
                "holding_type": holding_type,
                "source":       "Market",
                "buy_date":     "",
                "qty":          r["HDFC Qty"],
                "avg_cost":     0.0,       # not available from HDFC statement
            })
            added += 1

    save(fname_map[owner], stored)
    st.success(f"✅ Sync complete — {updated} holding(s) qty updated, {added} new holding(s) added.")
    if added:
        st.info("📝 New holdings added with avg cost = 0 and blank symbol. "
                "Please update them via the India Equity page.")
    st.rerun()

st.divider()
st.subheader("Raw HDFC Extract")
st.caption(f"Total rows extracted: {len(hdfc)}")
raw_fmt = {
    "qty":   lambda v: f"{v:,.3f}",
    "rate":  lambda v: ind_num(v),
    "value": lambda v: ind_num(v),
}
st.dataframe(pd.DataFrame(hdfc).style.format(raw_fmt), use_container_width=True, hide_index=True)
