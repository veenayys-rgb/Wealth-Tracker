"""Equity Recon Sandbox — HDFC Demat holding statement reconciliation.
Run with: streamlit run tools/equity_recon.py
"""
import sys, os, re, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import streamlit as st
import pdfplumber
import pandas as pd
from utils.config import load
from utils.fmt import ind_num

st.set_page_config(page_title="Equity Recon — Sandbox", page_icon="📋", layout="wide")
st.title("📋 Equity Recon — HDFC Demat Sandbox")
st.caption("Upload an HDFC Depository Holding Statement PDF. No data is written in sandbox mode.")

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


def extract_holdings(file_bytes: bytes) -> tuple[str, list[dict], list[dict]]:
    """Return (investor_name, holdings, debug_info) from HDFC PDF bytes.
    debug_info contains per-page line counts for sandbox diagnostics.
    """
    raw_pages, investor, debug = [], "", []

    with pdfplumber.open(file_bytes) as pdf:
        total_pages = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            t = page.extract_text() or ""
            raw_pages.append(t)
            lines_on_page  = [l.strip() for l in t.splitlines() if l.strip()]
            isin_lines     = [l for l in lines_on_page if re.match(r'^IN[A-Z0-9]{10}\s', l) or
                              re.match(r'^Free Balance\s+IN[A-Z0-9]{10}', l)]
            debug.append({
                "Page":          f"{i+1} of {total_pages}",
                "Total lines":   len(lines_on_page),
                "ISIN rows":     len(isin_lines),
                "Sample ISINs":  ", ".join(re.findall(r'IN[A-Z0-9]{10}', " ".join(isin_lines))[:3]),
            })

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
            "isin":    isin.upper(),
            "desc":    desc.strip(),
            "scrip":   "ETF/MF" if isin.startswith("INF") else "EQ",
            "qty":     qty,
            "rate":    rate,
            "value":   value,
        })

    return investor, records, debug


# ── UI ─────────────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
owner        = c1.selectbox("Owner", ["Vinay", "Harsh", "Anusha"])
holding_type = c2.selectbox("Holding Type", ["NRO", "NRE"])
uploaded     = c3.file_uploader("HDFC PDF", type=["pdf", "PDF"])

if not uploaded:
    st.info("Upload an HDFC Depository Holding Statement PDF to begin.")
    st.stop()

# ── Parse ──────────────────────────────────────────────────────────────────────
try:
    investor, hdfc, debug = extract_holdings(io.BytesIO(uploaded.read()))
except Exception as e:
    st.error(f"Failed to parse PDF: {e}")
    st.stop()

# ── Per-page debug table (always shown in sandbox) ─────────────────────────────
st.subheader("📄 Page-by-page breakdown")
st.caption("Use this to verify the last page is being parsed correctly.")
st.dataframe(pd.DataFrame(debug), use_container_width=True, hide_index=True)

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

# ── Build comparison ───────────────────────────────────────────────────────────
rows = []
for rec in hdfc:
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
st.divider()
total_val = sum(r["value"] for r in hdfc)
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Holdings in HDFC",  len(hdfc))
c2.metric("✅ Match",           sum(1 for r in rows if r["Status"] == "✅ Match"))
c3.metric("⚠️ Qty differs",     sum(1 for r in rows if "differ" in r["Status"]))
c4.metric("🆕 New",             sum(1 for r in rows if r["Status"] == "🆕 New"))
c5.metric("❌ Missing in HDFC", sum(1 for r in rows if "Missing" in r["Status"]))
c6.metric("HDFC Total Value",  ind_num(total_val))

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
st.subheader("Raw HDFC Extract")
st.caption(f"Total rows extracted: {len(hdfc)}")
raw_fmt = {
    "qty":   lambda v: f"{v:,.3f}",
    "rate":  lambda v: ind_num(v),
    "value": lambda v: ind_num(v),
}
st.dataframe(pd.DataFrame(hdfc).style.format(raw_fmt), use_container_width=True, hide_index=True)

st.info("🔒 Sandbox mode — no data is written to the tracker.")
