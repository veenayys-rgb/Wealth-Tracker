"""
Wealth Tracker — Main Fetcher Orchestrator
Triggered by watcher.py when Excel/manual trigger fires.
Runs: forex → AMFI → equity India → equity International → watchlist → history
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

    fetch_forex()            # AED/INR, USD/INR
    fetch_amfi_navs()        # MF + ETF NAVs from AMFI
    fetch_india()            # NSE/BSE equity prices
    fetch_international()    # ADX + US equity prices
    fetch_watchlist()        # Watchlist 52W data
    record_history()         # Daily snapshot (if market closed)

    elapsed = round(time.time() - start, 1)
    hr()
    print(f"✅  Done in {elapsed}s  —  {stamp()}")
    hr()
