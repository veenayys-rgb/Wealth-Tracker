"""
Equity price fetcher — India (NSE/BSE) + International (ADX/US)
Uses batch yf.download() for speed; individual fallback for failures.
"""
import json, time, datetime, ssl, os
import yfinance as yf
from db import upsert

ssl._create_default_https_context = ssl._create_unverified_context
os.environ["YFINANCE_CACHE_DIR"] = ""

ICLOUD      = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/WealthTracker")
CONFIG      = os.path.join(ICLOUD, "config")
YF_DELAY    = 0.5

SUFFIX = {"NSE": ".NS", "BSE": ".BO", "ADX": ".AD", "US": ""}


def load_json(filename: str) -> list:
    path = os.path.join(CONFIG, filename)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def batch_download(tickers: list[str], period: str = "1y") -> dict:
    """Download OHLCV for a list of tickers. Returns {ticker: {price, high52, low52}}."""
    if not tickers:
        return {}
    results = {}
    try:
        raw   = yf.download(
            tickers=tickers,
            period=period,
            auto_adjust=True,
            progress=False,
            group_by="ticker",
            threads=True,
        )
        multi = len(tickers) > 1
        for t in tickers:
            try:
                close = raw[t]["Close"].dropna() if multi else raw["Close"].dropna()
                highs = raw[t]["High"].dropna()  if multi else raw["High"].dropna()
                lows  = raw[t]["Low"].dropna()   if multi else raw["Low"].dropna()
                price = round(float(close.iloc[-1]), 4) if len(close) > 0 else 0
                if price > 0:
                    results[t] = {
                        "price":   price,
                        "high52":  round(float(highs.max()), 4) if len(highs) > 0 else None,
                        "low52":   round(float(lows.min()),  4) if len(lows)  > 0 else None,
                    }
            except Exception:
                pass
    except Exception as e:
        print(f"   ⚠️   Batch download failed: {e}")
    return results


def individual_fetch(sym: str, suffixes: list[str]) -> dict | None:
    """Single ticker fallback — tries each suffix in order."""
    for suffix in suffixes:
        try:
            info  = yf.Ticker(f"{sym}{suffix}").fast_info
            price = getattr(info, "last_price", None)
            if price and float(price) > 0:
                return {
                    "price":  round(float(price), 4),
                    "high52": round(float(info.year_high), 4) if info.year_high else None,
                    "low52":  round(float(info.year_low),  4) if info.year_low  else None,
                }
        except Exception:
            pass
        time.sleep(YF_DELAY)
    return None


# ── India Equity ──────────────────────────────────────────────────────────────

def fetch_india():
    holdings = load_json("equity_india.json")
    if not holdings:
        print("   ℹ️   equity_india.json empty — skipping")
        return

    symbols = [h["symbol"].upper() for h in holdings]
    nse_tickers = [f"{s}.NS" for s in symbols]

    print(f"\n📡  India Equity — batch NSE ({len(symbols)} stocks)…")
    fetched = batch_download(nse_tickers, period="1y")

    rows = []
    failed = []
    for sym in symbols:
        ns = f"{sym}.NS"
        if ns in fetched:
            d = fetched[ns]
            rows.append({"symbol": sym, "price": d["price"],
                         "fetched_at": datetime.datetime.utcnow().isoformat()})
            print(f"   ✅  {sym:<18} ₹{d['price']:>12,.4f}  [NSE]")
        else:
            failed.append(sym)

    # BSE fallback
    for sym in failed:
        d = individual_fetch(sym, [".BO", ".NS"])
        if d:
            rows.append({"symbol": sym, "price": d["price"],
                         "fetched_at": datetime.datetime.utcnow().isoformat()})
            print(f"   ✅  {sym:<18} ₹{d['price']:>12,.4f}  [BSE fallback]")
        else:
            print(f"   ❌  {sym:<18} Not found")

    # Deduplicate by symbol — keep last price fetched
    seen = {}
    for r in rows:
        seen[r["symbol"]] = r
    rows = list(seen.values())
    upsert("equity_india_prices", rows, conflict_col="symbol")
    print(f"   💾  {len(rows)}/{len(symbols)} India prices saved to Supabase")


# ── International Equity ──────────────────────────────────────────────────────

def fetch_international():
    holdings = load_json("equity_international.json")
    if not holdings:
        print("   ℹ️   equity_international.json empty — skipping")
        return

    # Group by region
    by_region: dict[str, list] = {}
    for h in holdings:
        by_region.setdefault(h["region"], []).append(h)

    rows = []
    print(f"\n📡  International Equity ({len(holdings)} stocks)…")

    for region, items in by_region.items():
        suffix  = SUFFIX.get(region, "")
        tickers = [f"{h['symbol'].upper()}{suffix}" for h in items]
        fetched = batch_download(tickers, period="1y")

        for h in items:
            sym    = h["symbol"].upper()
            ticker = f"{sym}{suffix}"
            if ticker in fetched:
                d = fetched[ticker]
                rows.append({
                    "symbol":     sym,
                    "region":     region,
                    "currency":   h["currency"],
                    "price":      d["price"],
                    "fetched_at": datetime.datetime.utcnow().isoformat(),
                })
                print(f"   ✅  {sym:<18} {h['currency']} {d['price']:>12,.4f}  [{region}]")
            else:
                d = individual_fetch(sym, [suffix] if suffix else [""])
                if d:
                    rows.append({
                        "symbol":     sym,
                        "region":     region,
                        "currency":   h["currency"],
                        "price":      d["price"],
                        "fetched_at": datetime.datetime.utcnow().isoformat(),
                    })
                    print(f"   ✅  {sym:<18} {h['currency']} {d['price']:>12,.4f}  [fallback]")
                else:
                    print(f"   ❌  {sym:<18} Not found [{region}]")

    upsert("equity_international_prices", rows, conflict_col="symbol")
    print(f"   💾  {len(rows)}/{len(holdings)} International prices saved to Supabase")


# ── Watchlist ─────────────────────────────────────────────────────────────────

def fetch_watchlist():
    items = load_json("watchlist.json")
    if not items:
        print("   ℹ️   watchlist.json empty — skipping")
        return

    print(f"\n📡  Watchlist ({len(items)} stocks)…")

    # Group by region for batch efficiency
    by_region: dict[str, list] = {}
    for item in items:
        by_region.setdefault(item["region"], []).append(item)

    rows = []
    for region, group in by_region.items():
        suffix  = SUFFIX.get(region, "")
        tickers = [f"{i['symbol'].upper()}{suffix}" for i in group]
        fetched = batch_download(tickers, period="1y")

        for item in group:
            sym    = item["symbol"].upper()
            ticker = f"{sym}{suffix}"
            if ticker in fetched:
                d = fetched[ticker]
                rows.append({
                    "symbol":        sym,
                    "last_close":    d["price"],
                    "current_price": d["price"],
                    "high_52w":      d["high52"],
                    "low_52w":       d["low52"],
                    "fetched_at":    datetime.datetime.utcnow().isoformat(),
                })
                print(f"   ✅  {sym:<18} 52W H: {d['high52']}  L: {d['low52']}")
            else:
                print(f"   ❌  {sym:<18} Not found")

    upsert("watchlist_prices", rows, conflict_col="symbol")
    print(f"   💾  {len(rows)}/{len(items)} Watchlist prices saved to Supabase")
