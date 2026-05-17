"""MF Recon — CAMS PDF reconciliation against stored holdings."""
import sys, os, re, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
import pdfplumber
import pandas as pd
from utils.config import load, save
from utils.fmt import ind_num

st.set_page_config(page_title="MF Recon | Wealth Tracker", page_icon="🔍", layout="wide")
st.title("🔍 MF Reconciliation — CAMS")
st.caption("Upload a CAMS Consolidated Account Summary PDF to compare with stored holdings.")
render_sidebar()

# ── Regex patterns ─────────────────────────────────────────────────────────────
NOISE_RE = re.compile(
    r'(Page\s+\d+\s+of\s+\d+|'
    r'\d{4}-eviL|'
    r'\d+\.\d+V:noisreV|'
    r'\d+-SWSACSMAC|'
    r'Consolidated Account Summary|'
    r'As on \d{2}-\w{3}-\d{4}|'
    r'Folio No\.\s+ISIN\s+Scheme Name.*?Registrar\s+\(INR\)\s+\(INR\)\s+\(INR\)|'
    r'Total\s+[\d,]+\.\d{2}\s+[\d,]+\.\d{2})',
    re.IGNORECASE | re.DOTALL
)
ENTRY_RE = re.compile(
    r'(\S+/\d+|\d+)\s*(INF[A-Z0-9]{9})\s+'
    r'(.+?)\s+'
    r'([\d,]+\.\d{3})\s+'
    r'([\d,]+\.\d{3})\s+'
    r'\d{2}-\w{3}-\d{4}\s+[\d,.]+\s+'
    r'[\d,]+\.\d{2}\s+'
    r'(CAMS|KFINTECH)\s*'
    r'(.*)',
    re.DOTALL
)
INVESTOR_RE = re.compile(r'Email Id:.*?\n([A-Z][a-zA-Z ]+)\n', re.DOTALL)


def extract_holdings(file_bytes: bytes, password: str) -> tuple[str, list[dict]]:
    """Return (investor_name, holdings_list) from CAMS PDF bytes."""
    raw_pages, investor = [], ""
    with pdfplumber.open(file_bytes, password=password) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                raw_pages.append(t)
    full_text = "\n".join(raw_pages)

    m = INVESTOR_RE.search(full_text)
    if m:
        investor = m.group(1).strip()

    if "Loads and Fees" in full_text:
        full_text = full_text[:full_text.index("Loads and Fees")]

    lines, joined = full_text.split("\n"), []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r'^(\S+/\d+|\d+)\s*INF', line):
            joined.append(line)
        elif joined:
            joined[-1] += " " + line

    records = []
    for line in joined:
        m = ENTRY_RE.search(line)
        if not m:
            continue
        folio, isin, scheme_before, cost_str, units_str, registrar, scheme_after = m.groups()
        cost  = float(cost_str.replace(",", ""))
        units = float(units_str.replace(",", ""))
        raw   = NOISE_RE.sub(" ", (scheme_before + " " + scheme_after).strip())
        raw   = re.sub(r'\s+', ' ', raw).strip()
        records.append({
            "folio":       folio.strip(),
            "isin":        isin.strip().upper(),
            "scheme_name": re.sub(r'^[^-]*-\s*', '', raw).strip(),
            "units":       units,
            "cost":        cost,
            "avg_nav":     round(cost / units, 4) if units > 0 else 0.0,
            "registrar":   registrar,
        })
    return investor, records


# ── UI ─────────────────────────────────────────────────────────────────────────
owner = st.selectbox("Owner", ["Vinay", "Harsh", "Anusha"])
c1, c2 = st.columns(2)
uploaded = c1.file_uploader("CAMS PDF", type="pdf")
password = c2.text_input("PDF Password", type="password")

if not uploaded:
    st.info("Upload a CAMS PDF to begin.")
    st.stop()
if not password:
    st.warning("Enter the PDF password.")
    st.stop()

# ── Parse ──────────────────────────────────────────────────────────────────────
try:
    investor, cams = extract_holdings(io.BytesIO(uploaded.read()), password)
except Exception as e:
    st.error(f"Failed to parse PDF: {e}")
    st.stop()

if not cams:
    st.error("No holdings found. Check password or PDF format.")
    st.stop()

st.success(f"Parsed **{len(cams)} funds** for **{investor or owner}**.")

# ── Load stored data ───────────────────────────────────────────────────────────
fname_map     = {"Vinay": "mutual_funds_vinay.json",
                 "Harsh": "mutual_funds_harsh.json",
                 "Anusha": "mutual_funds_anusha.json"}
stored        = load(fname_map[owner])
stored_by_key = {h["folio_no"]: h for h in stored if h.get("folio_no")}

# ── Build comparison ───────────────────────────────────────────────────────────
rows = []
for rec in cams:
    cams_key = f"{rec['folio']}_{rec['isin']}"
    s        = stored_by_key.get(cams_key)
    s_units  = float(s["units"])   if s else None
    s_avgnav = float(s["avg_nav"]) if s else None
    s_cost   = round(s_units * s_avgnav, 2) if s else None

    unit_diff = round(rec["units"]   - s_units,  4) if s_units  is not None else None
    cost_diff = round(rec["cost"]    - s_cost,   2) if s_cost   is not None else None
    nav_diff  = round(rec["avg_nav"] - s_avgnav, 4) if s_avgnav is not None else None

    if s is None:
        status = "🆕 New"
    elif unit_diff is not None and abs(unit_diff) > 0.001:
        status = "⚠️ Units differ"
    elif cost_diff is not None and abs(cost_diff) > 1:
        status = "⚠️ Cost differs"
    else:
        status = "✅ Match"

    rows.append({
        "Status":          status,
        "Unique Key":      cams_key,
        "ISIN":            rec["isin"],
        "CAMS Scheme":     rec["scheme_name"],
        "CAMS Units":      rec["units"],
        "Stored Units":    s_units,
        "Unit Diff":       unit_diff,
        "CAMS Avg NAV":    rec["avg_nav"],
        "Stored Avg NAV":  s_avgnav,
        "NAV Diff":        nav_diff,
        "CAMS Cost (₹)":   rec["cost"],
        "Stored Cost (₹)": s_cost,
        "Cost Diff (₹)":   cost_diff,
        "Registrar":       rec["registrar"],
    })

cams_keys = {f"{r['folio']}_{r['isin']}" for r in cams}
for h in stored:
    if h.get("folio_no") not in cams_keys:
        rows.append({
            "Status":          "❌ Missing in CAMS",
            "Unique Key":      h.get("folio_no", ""),
            "ISIN":            h["isin"].upper(),
            "CAMS Scheme":     "—",
            "CAMS Units":      None,
            "Stored Units":    float(h["units"]),
            "Unit Diff":       None,
            "CAMS Avg NAV":    None,
            "Stored Avg NAV":  float(h["avg_nav"]),
            "NAV Diff":        None,
            "CAMS Cost (₹)":   None,
            "Stored Cost (₹)": round(float(h["units"]) * float(h["avg_nav"]), 2),
            "Cost Diff (₹)":   None,
            "Registrar":       "—",
        })

df = pd.DataFrame(rows)

# ── Summary metrics ────────────────────────────────────────────────────────────
total_cost = sum(r["cost"] for r in cams)
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Funds in CAMS",     len(cams))
c2.metric("✅ Match",           sum(1 for r in rows if r["Status"] == "✅ Match"))
c3.metric("⚠️ Differ",          sum(1 for r in rows if "differ" in r["Status"]))
c4.metric("🆕 New",             sum(1 for r in rows if r["Status"] == "🆕 New"))
c5.metric("❌ Missing in CAMS", sum(1 for r in rows if "Missing" in r["Status"]))
c6.metric("CAMS Total Cost",   ind_num(total_cost))

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
    "CAMS Units":      lambda v: f"{v:,.3f}" if v is not None else "—",
    "Stored Units":    lambda v: f"{v:,.3f}" if v is not None else "—",
    "Unit Diff":       lambda v: f"{v:+,.3f}" if v is not None else "—",
    "CAMS Avg NAV":    lambda v: f"{v:,.4f}"  if v is not None else "—",
    "Stored Avg NAV":  lambda v: f"{v:,.4f}"  if v is not None else "—",
    "NAV Diff":        lambda v: f"{v:+,.4f}" if v is not None else "—",
    "CAMS Cost (₹)":   lambda v: ind_num(v)   if v is not None else "—",
    "Stored Cost (₹)": lambda v: ind_num(v)   if v is not None else "—",
    "Cost Diff (₹)":   lambda v: ind_num(v)   if v is not None else "—",
}

def _colour(v):
    if not isinstance(v, str): return ""
    if v.startswith("+"): return "color:green"
    if v.startswith("-"): return "color:red"
    return ""

st.dataframe(
    view.style.format(fmt)
              .map(_colour, subset=["Unit Diff", "NAV Diff", "Cost Diff (₹)"]),
    use_container_width=True,
    hide_index=True,
)

st.divider()

# ── Sync ───────────────────────────────────────────────────────────────────────
to_update = [r for r in rows if "differ" in r["Status"]]
to_add    = [r for r in rows if r["Status"] == "🆕 New"]
missing   = [r for r in rows if "Missing" in r["Status"]]

if missing:
    names = ", ".join(r["Unique Key"] for r in missing)
    st.warning(f"⚠️ {len(missing)} fund(s) in tracker not found in CAMS — please review manually: {names}")

can_sync = len(to_update) + len(to_add) > 0
if can_sync:
    st.info(f"Ready to sync: **{len(to_update)}** fund(s) to update  |  **{len(to_add)}** new fund(s) to add")

if st.button("🔄 Sync to Tracker", disabled=not can_sync, type="primary"):
    cams_by_key = {f"{r['folio']}_{r['isin']}": r for r in cams}

    updated = 0
    for h in stored:
        crec = cams_by_key.get(h.get("folio_no", ""))
        if crec and abs(float(h["units"]) - crec["units"]) > 0.001:
            h["units"]   = crec["units"]
            h["avg_nav"] = crec["avg_nav"]
            updated += 1

    added, existing_keys = 0, {h.get("folio_no", "") for h in stored}
    for r in to_add:
        if r["Unique Key"] not in existing_keys:
            stored.append({
                "folio_no":  r["Unique Key"],
                "isin":      r["ISIN"],
                "fund_name": r["CAMS Scheme"],
                "units":     r["CAMS Units"],
                "avg_nav":   r["CAMS Avg NAV"],
            })
            added += 1

    save(fname_map[owner], stored)
    st.success(f"✅ Sync complete — {updated} fund(s) updated, {added} new fund(s) added.")
    st.rerun()

st.divider()
st.subheader("Raw CAMS Extract")
raw_fmt = {
    "cost":    lambda v: ind_num(v),
    "units":   lambda v: f"{v:,.3f}",
    "avg_nav": lambda v: f"{v:,.4f}",
}
st.dataframe(pd.DataFrame(cams).style.format(raw_fmt), use_container_width=True, hide_index=True)
