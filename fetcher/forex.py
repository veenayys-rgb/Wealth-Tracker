"""Forex rate fetcher — AED/INR and USD/INR via yfinance."""
import datetime, time, ssl, os
import yfinance as yf
from db import upsert

ssl._create_default_https_context = ssl._create_unverified_context
os.environ["YFINANCE_CACHE_DIR"] = ""

PAIRS   = [("AED_INR", "AEDINR=X"), ("USD_INR", "USDINR=X")]
INDICES = [("NIFTY50", "^NSEI"),    ("SENSEX",  "^BSESN")]


def fetch_forex():
    print(f"\n📡  Forex rates…")
    rows = []
    for pair, ticker in PAIRS:
        try:
            info  = yf.Ticker(ticker).fast_info
            rate  = getattr(info, "last_price", None)
            if rate and float(rate) > 0:
                rows.append({
                    "pair":       pair,
                    "rate":       round(float(rate), 6),
                    "fetched_at": datetime.datetime.utcnow().isoformat(),
                })
                print(f"   ✅  {pair:<10} = {rate:.4f}")
            else:
                print(f"   ⚠️   {pair}: no rate returned")
        except Exception as e:
            print(f"   ❌  {pair}: {e}")
        time.sleep(0.5)

    print(f"\n📡  Market indices…")
    for key, ticker in INDICES:
        try:
            info  = yf.Ticker(ticker).fast_info
            price = getattr(info, "last_price", None)
            if price and float(price) > 0:
                rows.append({
                    "pair":       key,
                    "rate":       round(float(price), 2),
                    "fetched_at": datetime.datetime.utcnow().isoformat(),
                })
                print(f"   ✅  {key:<10} = {float(price):,.2f}")
            else:
                print(f"   ⚠️   {key}: no price returned")
        except Exception as e:
            print(f"   ❌  {key}: {e}")
        time.sleep(0.5)

    upsert("forex_rates", rows, conflict_col="pair")
    print(f"   💾  {len(rows)} rates/indices saved")
