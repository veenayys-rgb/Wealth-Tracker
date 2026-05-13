"""
Mutual Fund + ETF NAV fetcher — AMFI India
Fetches NAVAll.txt once and looks up all ISINs in one pass.
"""
import json, datetime, os, urllib.request, ssl
from db import upsert

AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
ICLOUD   = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/WealthTracker")
CONFIG   = os.path.join(ICLOUD, "config")

MF_FILES = [
    "mutual_funds_vinay.json",
    "mutual_funds_harsh.json",
    "mutual_funds_anusha.json",
]


def load_json(filename: str) -> list:
    path = os.path.join(CONFIG, filename)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def fetch_amfi_navs():
    # Collect all unique ISINs across all three MF files
    all_isins: dict[str, str] = {}   # isin → fund_name
    for fname in MF_FILES:
        for h in load_json(fname):
            isin = str(h.get("isin", "")).strip().upper()
            if isin:
                all_isins[isin] = h.get("fund_name", "")

    if not all_isins:
        print("   ℹ️   No MF ISINs found — skipping")
        return

    print(f"\n📡  MF/ETF NAVs — {len(all_isins)} ISINs via AMFI…")

    # Download AMFI NAVAll.txt
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        resp  = urllib.request.urlopen(AMFI_URL, timeout=30, context=ctx)
        lines = resp.read().decode("utf-8", errors="ignore").splitlines()
        print(f"   ✅  {len(lines):,} lines from AMFI")
    except Exception as e:
        print(f"   ❌  AMFI download failed: {e}")
        return

    # Build ISIN → {nav, name, date} index
    amfi_index: dict[str, dict] = {}
    for line in lines:
        parts = line.strip().split(";")
        if len(parts) < 6:
            continue
        try:
            nav      = float(parts[4].strip())
            name     = parts[3].strip()
            nav_date = parts[5].strip()
            for isin in [parts[1].strip().upper(), parts[2].strip().upper()]:
                if isin:
                    amfi_index[isin] = {"nav": nav, "name": name, "date": nav_date}
        except (ValueError, IndexError):
            pass

    # Match user ISINs
    rows = []
    ok, failed = 0, 0
    for isin, user_name in all_isins.items():
        if isin in amfi_index:
            d = amfi_index[isin]
            rows.append({
                "isin":       isin,
                "nav":        d["nav"],
                "nav_date":   d["date"],
                "amfi_name":  d["name"],
                "fetched_at": datetime.datetime.utcnow().isoformat(),
            })
            print(f"   ✅  {isin}  NAV ₹{d['nav']:.4f}  ({d['date']})")
            ok += 1
        else:
            print(f"   ❌  {isin}  ({user_name[:40]}) — not found in AMFI")
            failed += 1

    upsert("mf_navs", rows, conflict_col="isin")
    print(f"   💾  {ok}/{len(all_isins)} NAVs saved | {failed} not found")
