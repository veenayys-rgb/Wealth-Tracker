"""Shared sidebar — Refresh Prices button shown on every page."""
import datetime, time, ssl, urllib.request
import streamlit as st
import yfinance as yf
from utils.db     import service_upsert
from utils.config import load

SUFFIX = {"India": ".NS", "UAE": ".AD", "US": "", "UK": ".L", "Other": ""}


def render_sidebar():
    with st.sidebar:
        st.markdown("---")
        if st.button("🔄 Refresh Prices", use_container_width=True, type="primary"):
            with st.spinner("Fetching latest prices…"):
                try:
                    _updated = 0

                    # Forex
                    for pair, ticker in [("AED_INR", "AEDINR=X"), ("USD_INR", "USDINR=X")]:
                        try:
                            rate = getattr(yf.Ticker(ticker).fast_info, "last_price", None)
                            if rate and float(rate) > 0:
                                service_upsert("forex_rates",
                                               [{"pair": pair, "rate": round(float(rate), 6),
                                                 "fetched_at": datetime.datetime.utcnow().isoformat()}],
                                               conflict_col="pair")
                        except Exception:
                            pass
                        time.sleep(0.3)

                    # India Equity
                    holdings_eq = load("equity_india.json")
                    if holdings_eq:
                        syms    = list({h["symbol"].upper() for h in holdings_eq})
                        tickers = [f"{s}.NS" for s in syms]
                        try:
                            ssl._create_default_https_context = ssl._create_unverified_context
                            raw   = yf.download(tickers, period="2d", auto_adjust=True,
                                                progress=False, group_by="ticker", threads=True)
                            multi = len(tickers) > 1
                            eq_rows = []
                            for s, t in zip(syms, tickers):
                                try:
                                    closes = raw[t]["Close"].dropna() if multi else raw["Close"].dropna()
                                    price  = round(float(closes.iloc[-1]), 4) if len(closes) > 0 else 0
                                    if price > 0:
                                        eq_rows.append({"symbol": s, "price": price,
                                                        "fetched_at": datetime.datetime.utcnow().isoformat()})
                                except Exception:
                                    pass
                            if eq_rows:
                                service_upsert("equity_india_prices", eq_rows, conflict_col="symbol")
                                _updated += len(eq_rows)
                        except Exception:
                            pass

                    # Mutual Funds (AMFI)
                    holdings_mf = (load("mutual_funds_vinay.json") +
                                   load("mutual_funds_harsh.json") +
                                   load("mutual_funds_anusha.json"))
                    all_isins = {h.get("isin", "").upper() for h in holdings_mf if h.get("isin")}
                    if all_isins:
                        try:
                            ctx = ssl.create_default_context()
                            ctx.check_hostname = False
                            ctx.verify_mode    = ssl.CERT_NONE
                            resp  = urllib.request.urlopen(
                                "https://www.amfiindia.com/spages/NAVAll.txt", timeout=30, context=ctx)
                            lines = resp.read().decode("utf-8", errors="ignore").splitlines()
                            amfi  = {}
                            for line in lines:
                                parts = line.strip().split(";")
                                if len(parts) < 6:
                                    continue
                                try:
                                    nav  = float(parts[4].strip())
                                    for isin in [parts[1].strip().upper(), parts[2].strip().upper()]:
                                        if isin:
                                            amfi[isin] = {"nav": nav, "name": parts[3].strip(),
                                                          "date": parts[5].strip()}
                                except (ValueError, IndexError):
                                    pass
                            mf_rows = []
                            for isin in all_isins:
                                if isin in amfi:
                                    d = amfi[isin]
                                    mf_rows.append({"isin": isin, "nav": d["nav"],
                                                    "nav_date": d["date"], "amfi_name": d["name"],
                                                    "fetched_at": datetime.datetime.utcnow().isoformat()})
                            if mf_rows:
                                service_upsert("mf_navs", mf_rows, conflict_col="isin")
                                _updated += len(mf_rows)
                        except Exception:
                            pass

                    # Watchlist
                    holdings_wl = load("watchlist.json")
                    if holdings_wl:
                        by_region: dict = {}
                        for item in holdings_wl:
                            by_region.setdefault(item.get("region", "Other"), []).append(item)
                        wl_rows = []
                        for region, group in by_region.items():
                            suffix  = SUFFIX.get(region, "")
                            tickers = [f"{i['symbol'].upper()}{suffix}" for i in group]
                            try:
                                raw   = yf.download(tickers, period="1y", auto_adjust=True,
                                                    progress=False, group_by="ticker", threads=True)
                                multi = len(tickers) > 1
                                for item, t in zip(group, tickers):
                                    sym = item["symbol"].upper()
                                    try:
                                        closes = raw[t]["Close"].dropna() if multi else raw["Close"].dropna()
                                        highs  = raw[t]["High"].dropna()  if multi else raw["High"].dropna()
                                        lows   = raw[t]["Low"].dropna()   if multi else raw["Low"].dropna()
                                        if len(closes) > 0:
                                            wl_rows.append({
                                                "symbol":        sym,
                                                "last_close":    round(float(closes.iloc[-1]), 4),
                                                "current_price": round(float(closes.iloc[-1]), 4),
                                                "high_52w":      round(float(highs.max()), 4),
                                                "low_52w":       round(float(lows.min()), 4),
                                                "fetched_at":    datetime.datetime.utcnow().isoformat(),
                                            })
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                        if wl_rows:
                            service_upsert("watchlist_prices", wl_rows, conflict_col="symbol")
                            _updated += len(wl_rows)

                    st.success(f"✅ Prices updated ({_updated} securities).")
                    st.rerun()
                except Exception as e:
                    st.error(f"Refresh failed: {e}")
        st.markdown("---")
