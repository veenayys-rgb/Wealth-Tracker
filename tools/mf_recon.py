"""MF Recon Sandbox — parse CAMS PDF and compare with stored holdings.
Run with: streamlit run tools/mf_recon.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import streamlit as st
import pdfplumber
import pandas as pd
import re
from utils.config import load
from utils.db import fetch
from utils.fmt import ind_num

st.set_page_config(page_title="MF Recon — CAMS Sandbox", page_icon="🔍", layout="wide")
st.title("🔍 MF Recon — CAMS PDF Sandbox")
st.caption("Upload a CAMS Consolidated Account Summary PDF to compare with stored holdings.")

# ── Row pattern ───────────────────────────────────────────────────────────────
# Handles both spaced and concatenated folio+ISIN (e.g. 91081412715/0INF846K016E3)
ROW_RE = re.compile(
    r'^([\w/]+?)\s*(INF[A-Z0-9]{9})\s+(.+?)\s+'
    r'([\d,]+\.\d{3})\s+([\d,]+\.\d{3})\s+'
    r'(\d{2}-\w{3}-\d{4})\s+([\d,]+\.?\d*)\s+'
    r'([\d,]+\.\d{2})\s+(CAMS|KFINTECH)$'
)
INVESTOR_RE = re.compile(r'^([A-Z][a-z]+ [A-Z][a-z]+)')


def parse_cams(file_bytes: bytes, password: str) -> tuple[str, list[dict]]:
    """Return (investor_name, list_of_holdings) from CAMS PDF bytes."""
    investor = ""
    records = []
    with pdfplumber.open(file_bytes, password=password) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            # Stop parsing at Loads & Fees section (pages 3+)
            if "Loads and Fees" in text:
                text = text[:text.index("Loads and Fees")]
            # Extract investor name from first page header
            if not investor:
                for line in text.splitlines():
                    line = line.strip()
                    m = INVESTOR_RE.match(line)
                    if m and "Email" not in line and "Summary" not in line:
                        investor = m.group(1)
                        break
            for line in text.splitlines():
                m = ROW_RE.match(line.strip())
                if m:
                    folio, isin, scheme, cost, units, nav_date, nav, mkt_val, registrar = m.groups()
                    cost_f  = float(cost.replace(",", ""))
                    units_f = float(units.replace(",", ""))
                    records.append({
                        "folio":        folio.strip(),
                        "isin":         isin.strip(),
                        "scheme":       scheme.strip(),
                        "cost":         cost_f,
                        "units":        units_f,
                        "nav_date":     nav_date,
                        "nav":          float(nav.replace(",", "")),
                        "market_value": float(mkt_val.replace(",", "")),
                        "avg_nav":      round(cost_f / units_f, 4) if units_f > 0 else 0.0,
                        "registrar":    registrar,
                    })
    return investor, records


# ── UI ────────────────────────────────────────────────────────────────────────
owner = st.selectbox("Owner", ["Vinay", "Harsh", "Anusha"])
col1, col2 = st.columns(2)
uploaded = col1.file_uploader("CAMS PDF", type="pdf")
password = col2.text_input("PDF Password", type="password")

if not uploaded:
    st.info("Upload a CAMS PDF to begin.")
    st.stop()
if not password:
    st.warning("Enter the PDF password.")
    st.stop()

# ── Parse PDF ─────────────────────────────────────────────────────────────────
try:
    import io
    investor, cams_records = parse_cams(io.BytesIO(uploaded.read()), password)
except Exception as e:
    st.error(f"Failed to parse PDF: {e}")
    st.stop()

if not cams_records:
    st.error("No holdings found. Check password or PDF format.")
    st.stop()

st.success(f"Parsed **{len(cams_records)} funds** for **{investor or owner}** from CAMS PDF.")

# ── Load stored holdings ──────────────────────────────────────────────────────
fname_map = {"Vinay": "mutual_funds_vinay.json",
             "Harsh": "mutual_funds_harsh.json",
             "Anusha": "mutual_funds_anusha.json"}
stored = load(fname_map[owner])
stored_by_isin = {h["isin"].upper(): h for h in stored}
navs_by_isin   = {r["isin"].upper(): r for r in fetch("mf_navs")}

# ── Build comparison table ────────────────────────────────────────────────────
rows = []
for rec in cams_records:
    isin    = rec["isin"].upper()
    stored_h = stored_by_isin.get(isin)
    nav_r    = navs_by_isin.get(isin, {})

    s_units  = float(stored_h["units"])   if stored_h else None
    s_cost   = float(stored_h["avg_nav"]) * s_units if stored_h and s_units else None
    s_avgnav = float(stored_h["avg_nav"]) if stored_h else None

    unit_diff = round(rec["units"] - s_units, 4) if s_units is not None else None
    cost_diff = round(rec["cost"]  - s_cost,  2) if s_cost  is not None else None

    status = "✅ Match"
    if stored_h is None:
        status = "🆕 New (not in tracker)"
    elif unit_diff and abs(unit_diff) > 0.001:
        status = "⚠️ Units differ"
    elif cost_diff and abs(cost_diff) > 1:
        status = "⚠️ Cost differs"

    rows.append({
        "Status":           status,
        "ISIN":             isin,
        "CAMS Scheme":      rec["scheme"],
        "CAMS Units":       rec["units"],
        "Stored Units":     s_units,
        "Unit Diff":        unit_diff,
        "CAMS Cost (₹)":    rec["cost"],
        "Stored Cost (₹)":  s_cost,
        "Cost Diff (₹)":    cost_diff,
        "CAMS Avg NAV":     rec["avg_nav"],
        "Stored Avg NAV":   s_avgnav,
        "CAMS Mkt Val (₹)": rec["market_value"],
        "Folio":            rec["folio"],
        "Registrar":        rec["registrar"],
    })

# Also flag funds in tracker not in CAMS
cams_isins = {r["isin"].upper() for r in cams_records}
for h in stored:
    if h["isin"].upper() not in cams_isins:
        rows.append({
            "Status":           "❌ Missing in CAMS",
            "ISIN":             h["isin"].upper(),
            "CAMS Scheme":      "—",
            "CAMS Units":       None,
            "Stored Units":     float(h["units"]),
            "Unit Diff":        None,
            "CAMS Cost (₹)":    None,
            "Stored Cost (₹)":  float(h["avg_nav"]) * float(h["units"]),
            "Cost Diff (₹)":    None,
            "CAMS Avg NAV":     None,
            "Stored Avg NAV":   float(h["avg_nav"]),
            "CAMS Mkt Val (₹)": None,
            "Folio":            h.get("folio_no", ""),
            "Registrar":        "—",
        })

df = pd.DataFrame(rows)

# ── Summary metrics ───────────────────────────────────────────────────────────
total_cams_cost = sum(r["cost"] for r in cams_records)
total_cams_mv   = sum(r["market_value"] for r in cams_records)
matches   = sum(1 for r in rows if r["Status"] == "✅ Match")
new_funds = sum(1 for r in rows if "New" in r["Status"])
diffs     = sum(1 for r in rows if "differ" in r["Status"])
missing   = sum(1 for r in rows if "Missing" in r["Status"])

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Funds in CAMS",    len(cams_records))
c2.metric("✅ Match",          matches)
c3.metric("⚠️ Differ",         diffs)
c4.metric("🆕 New",            new_funds)
c5.metric("❌ Missing in CAMS", missing)
c6.metric("CAMS Total Cost",  ind_num(total_cams_cost))

st.divider()

# ── Comparison table ──────────────────────────────────────────────────────────
st.subheader("Comparison")

status_filter = st.multiselect(
    "Filter by status",
    options=df["Status"].unique().tolist(),
    default=df["Status"].unique().tolist(),
)
view = df[df["Status"].isin(status_filter)].copy()

num_fmt = {
    "CAMS Units":       lambda v: f"{v:,.3f}" if v is not None else "—",
    "Stored Units":     lambda v: f"{v:,.3f}" if v is not None else "—",
    "Unit Diff":        lambda v: f"{v:+,.3f}" if v is not None else "—",
    "CAMS Cost (₹)":    lambda v: ind_num(v) if v is not None else "—",
    "Stored Cost (₹)":  lambda v: ind_num(v) if v is not None else "—",
    "Cost Diff (₹)":    lambda v: ind_num(v) if v is not None else "—",
    "CAMS Avg NAV":     lambda v: f"{v:,.4f}" if v is not None else "—",
    "Stored Avg NAV":   lambda v: f"{v:,.4f}" if v is not None else "—",
    "CAMS Mkt Val (₹)": lambda v: ind_num(v) if v is not None else "—",
}

def _colour(v):
    if not isinstance(v, str): return ""
    if v.startswith("+"):  return "color:green"
    if v.startswith("-"):  return "color:red"
    return ""

st.dataframe(
    view.style.format(num_fmt)
              .map(_colour, subset=["Unit Diff", "Cost Diff (₹)"]),
    use_container_width=True,
    hide_index=True,
)

st.divider()
st.subheader("Raw CAMS Data")
raw_df = pd.DataFrame(cams_records)
raw_fmt = {
    "cost":         lambda v: ind_num(v),
    "units":        lambda v: f"{v:,.3f}",
    "nav":          lambda v: f"{v:,.4f}",
    "market_value": lambda v: ind_num(v),
    "avg_nav":      lambda v: f"{v:,.4f}",
}
st.dataframe(raw_df.style.format(raw_fmt), use_container_width=True, hide_index=True)
