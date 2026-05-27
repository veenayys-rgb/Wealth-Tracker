"""
Wealth Tracker — Main Fetcher Orchestrator
Triggered by watcher.py when Excel/manual trigger fires.
Runs: forex → AMFI → equity India → equity International → watchlist → history
Exits with code 1 if India equity has holdings but saved 0 prices.
"""
import sys, os, datetime, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from forex        import fetch_forex
from mutual_funds import fetch_amfi_navs
from equity       import fetch_india, fetch_international, fetch_watchlist
from history      import record_history

def hr():    print("─" * 62)
def stamp(): return datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S")


if __name__ == "__main__":
    hr()
    print("💰  WEALTH TRACKER — FULL REFRESH")
    print(f"    {stamp()}")
    hr()

    start = time.time()

    fetch_forex()                                    # AED/INR, USD/INR, Nifty, Sensex
    mf_ok,    mf_total    = fetch_amfi_navs()        # MF + ETF NAVs from AMFI
    eq_ok,    eq_total    = fetch_india()             # NSE/BSE equity prices
    fetch_international()                            # ADX + US equity prices
    fetch_watchlist()                                # Watchlist 52W data
    record_history()                                 # Daily snapshot (if market closed)

    elapsed = round(time.time() - start, 1)
    hr()
    print(f"📊  SUMMARY")
    print(f"   MF NAVs     : {mf_ok}/{mf_total} updated")
    print(f"   India Equity: {eq_ok}/{eq_total} updated")
    print(f"✅  Done in {elapsed}s  —  {stamp()}")
    hr()

    # Fail loudly if India equity has holdings but nothing was saved — this
    # makes GitHub Actions mark the run as ❌ FAILURE and sends you an email.
    if eq_total > 0 and eq_ok == 0:
        print("❌  ERROR: India equity has holdings but 0 prices were saved.")
        print("   Check yfinance / NSE connectivity from the runner.")
        sys.exit(1)
