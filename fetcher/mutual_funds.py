"""
Mutual Fund + ETF NAV fetcher — AMFI India
Fetches NAVAll.txt once and looks up all ISINs in one pass.
"""
import datetime, urllib.request, ssl
from db import upsert, fetch_cfg

AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"


def fetch_amfi_navs() -> tuple[int, int]:
    # Collect all unique ISINs from Supabase cfg_mutual_funds
    all_isins: dict[str, str] = {}   # isin → fund_name
    for h in fetch_cfg("cfg_mutual_funds"):
        isin = str(h.get("isin", "")).strip().upper()
        if isin:
            all_isins[isin] = h.get("fund_name", "")

    if not all_isins:
        print("   ℹ️   No MF ISINs found — skipping")
        return 0, 0

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
        return 0, len(all_isins)

    # Build ISIN → {nav, name, date} index
    # AMFI NAVAll.txt has 8 columns (as of 2025):
    #   Code; ISIN Growth; ISIN Div-Reinv; Scheme Name; Plan; Option; NAV; Date
    amfi_index: dict[str, dict] = {}
    for line in lines:
        parts = line.strip().split(";")
        if len(parts) < 8:
            continue
        try:
            nav      = float(parts[6].strip())
            name     = parts[3].strip()
            nav_date = parts[7].strip()
            for isin in [parts[1].strip().upper(), parts[2].strip().upper()]:
                if isin and isin != "-":
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
    return ok, len(all_isins)
