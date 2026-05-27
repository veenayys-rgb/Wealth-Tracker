"""Shared sidebar — Refresh Prices button shown on every page."""
import datetime, time, ssl, urllib.request
import streamlit as st
import yfinance as yf
from utils.db     import service_upsert, fetch, fetch_one
from utils.config import load

SUFFIX   = {"India": ".NS", "UAE": ".AD", "US": "", "UK": ".L", "Other": ""}
_IST_TZ  = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
_FAMILY  = {"Vinay", "Harsh", "Anusha"}


def _market_closed() -> bool:
    """True if NSE market is currently closed (after 3:30 PM IST or weekend)."""
    now = datetime.datetime.now(_IST_TZ)
    if now.weekday() >= 5:
        return True
    return now >= now.replace(hour=15, minute=30, second=0, microsecond=0)


def _record_history_snapshot() -> tuple[dict, dict]:
    """Compute today's portfolio snapshot and upsert to portfolio_history tables.
    Returns (family_row, mom_row)."""
    today     = datetime.datetime.now(_IST_TZ).date().isoformat()
    eq_prices = {r["symbol"]: float(r["price"]) for r in fetch("equity_india_prices")}
    mf_navs   = {r["isin"]:   float(r["nav"])   for r in fetch("mf_navs")}

    # ── Family equity ─────────────────────────────────────────────────
    eq_inv = eq_cv = 0.0
    for h in load("equity_india.json"):
        if h.get("owner") and h["owner"] not in _FAMILY:
            continue
        sym   = h["symbol"].upper()
        qty   = float(h.get("qty", 0))
        cost  = float(h.get("avg_cost", 0))
        price = eq_prices.get(sym, 0)
        eq_inv += qty * cost
        eq_cv  += qty * price if price > 0 else qty * cost

    # ── Family MF ─────────────────────────────────────────────────────
    mf_data = {}
    for owner in ["Vinay", "Harsh", "Anusha"]:
        inv = cv = 0.0
        for h in load(f"mutual_funds_{owner.lower()}.json"):
            isin  = h.get("isin", "").upper()
            units = float(h.get("units", 0))
            anav  = float(h.get("avg_nav", 0))
            nav   = mf_navs.get(isin, 0)
            inv  += units * anav
            cv   += units * nav if nav > 0 else units * anav
        mf_data[owner.lower()] = {"invested": round(inv, 2), "cv": round(cv, 2)}

    total_inv = eq_inv + sum(v["invested"] for v in mf_data.values())
    total_cv  = eq_cv  + sum(v["cv"]       for v in mf_data.values())
    gain      = total_cv - total_inv
    ret_pct   = round(gain / total_inv * 100, 4) if total_inv > 0 else 0

    family_row = {
        "date":            today,
        "shares_invested": round(eq_inv, 2),
        "shares_cv":       round(eq_cv, 2),
        "mf_inv_vinay":    mf_data["vinay"]["invested"],
        "mf_cv_vinay":     mf_data["vinay"]["cv"],
        "mf_inv_harsh":    mf_data["harsh"]["invested"],
        "mf_cv_harsh":     mf_data["harsh"]["cv"],
        "mf_inv_anusha":   mf_data["anusha"]["invested"],
        "mf_cv_anusha":    mf_data["anusha"]["cv"],
        "total_invested":  round(total_inv, 2),
        "total_cv":        round(total_cv, 2),
        "gain_loss":       round(gain, 2),
        "return_pct":      ret_pct,
    }
    service_upsert("portfolio_history", [family_row], conflict_col="date")

    # ── Mom equity ────────────────────────────────────────────────────
    mom_eq_inv = mom_eq_cv = 0.0
    for h in load("mom_equity_india.json"):
        sym   = h["symbol"].upper()
        qty   = float(h.get("qty", 0))
        cost  = float(h.get("avg_cost", 0))
        price = eq_prices.get(sym, 0)
        mom_eq_inv += qty * cost
        mom_eq_cv  += qty * price if price > 0 else qty * cost

    # ── Mom MF ───────────────────────────────────────────────────────
    mom_mf_inv = mom_mf_cv = 0.0
    for h in load("mom_mutual_funds.json"):
        isin  = h.get("isin", "").upper()
        units = float(h.get("units", 0))
        anav  = float(h.get("avg_nav", 0))
        nav   = mf_navs.get(isin, 0)
        mom_mf_inv += units * anav
        mom_mf_cv  += units * nav if nav > 0 else units * anav

    mom_total_inv = mom_eq_inv + mom_mf_inv
    mom_total_cv  = mom_eq_cv  + mom_mf_cv
    mom_gain      = mom_total_cv - mom_total_inv
    mom_ret       = round(mom_gain / mom_total_inv * 100, 4) if mom_total_inv > 0 else 0

    mom_row = {
        "date":           today,
        "eq_invested":    round(mom_eq_inv, 2),
        "eq_cv":          round(mom_eq_cv, 2),
        "mf_invested":    round(mom_mf_inv, 2),
        "mf_cv":          round(mom_mf_cv, 2),
        "total_invested": round(mom_total_inv, 2),
        "total_cv":       round(mom_total_cv, 2),
        "gain_loss":      round(mom_gain, 2),
        "return_pct":     mom_ret,
    }
    service_upsert("portfolio_history_mom", [mom_row], conflict_col="date")

    return family_row, mom_row


_MOBILE_CSS = """
<style>
@media (max-width: 768px) {
    /* Stack all st.columns vertically */
    [data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }
    /* Remove wide-layout horizontal padding */
    .block-container {
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        max-width: 100% !important;
    }
    /* Scrollable tab bar (don't wrap, just scroll) */
    [data-testid="stTabs"] [role="tablist"] {
        overflow-x: auto !important;
        flex-wrap: nowrap !important;
    }
    /* Scrollable data tables */
    [data-testid="stDataFrame"] > div {
        overflow-x: auto !important;
    }
    /* Wrap horizontal radio buttons (period selector) */
    [data-testid="stRadio"] > div {
        flex-wrap: wrap !important;
    }
    /* Slightly smaller metric text */
    [data-testid="metric-container"] {
        font-size: 0.85em !important;
    }
}
</style>
"""


def render_sidebar():
    st.markdown(_MOBILE_CSS, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown("---")
        if st.button("🔄 Refresh Prices", use_container_width=True, type="primary"):
            with st.spinner("Fetching latest prices…"):
                try:
                    _updated = 0

                    # Forex + Market Indices
                    _rate_pairs = [
                        ("AED_INR", "AEDINR=X", 6),
                        ("USD_INR", "USDINR=X", 6),
                        ("NIFTY50", "^NSEI",    2),
                        ("SENSEX",  "^BSESN",   2),
                    ]
                    for pair, ticker, decimals in _rate_pairs:
                        try:
                            rate = getattr(yf.Ticker(ticker).fast_info, "last_price", None)
                            if rate and float(rate) > 0:
                                service_upsert("forex_rates",
                                               [{"pair": pair, "rate": round(float(rate), decimals),
                                                 "fetched_at": datetime.datetime.utcnow().isoformat()}],
                                               conflict_col="pair")
                        except Exception:
                            pass
                        time.sleep(0.3)

                    # India Equity — NSE batch, then BSE fallback for misses
                    holdings_eq = load("equity_india.json")
                    if holdings_eq:
                        syms = list({h["symbol"].upper() for h in holdings_eq if h.get("symbol","").strip()})
                        ssl._create_default_https_context = ssl._create_unverified_context
                        eq_rows   = []
                        nse_miss  = []

                        # ── NSE batch ──────────────────────────────────────────
                        nse_tickers = [f"{s}.NS" for s in syms]
                        try:
                            raw   = yf.download(nse_tickers, period="2d", auto_adjust=True,
                                                progress=False, group_by="ticker", threads=True)
                            multi = len(nse_tickers) > 1
                            for s, t in zip(syms, nse_tickers):
                                try:
                                    closes = raw[t]["Close"].dropna() if multi else raw["Close"].dropna()
                                    price  = round(float(closes.iloc[-1]), 4) if len(closes) > 0 else 0
                                    if price > 0:
                                        eq_rows.append({"symbol": s, "price": price,
                                                        "fetched_at": datetime.datetime.utcnow().isoformat()})
                                    else:
                                        nse_miss.append(s)
                                except Exception:
                                    nse_miss.append(s)
                        except Exception:
                            nse_miss = syms   # full batch failed — retry all via BSE

                        # ── BSE individual fallback ────────────────────────────
                        for s in nse_miss:
                            try:
                                info  = yf.Ticker(f"{s}.BO").fast_info
                                price = getattr(info, "last_price", None)
                                if price and float(price) > 0:
                                    eq_rows.append({"symbol": s, "price": round(float(price), 4),
                                                    "fetched_at": datetime.datetime.utcnow().isoformat()})
                            except Exception:
                                pass
                            time.sleep(0.3)

                        if eq_rows:
                            deduped = list({r["symbol"]: r for r in eq_rows}.values())
                            service_upsert("equity_india_prices", deduped, conflict_col="symbol")
                            _updated += len(deduped)

                    # Mutual Funds (AMFI)
                    holdings_mf = (load("mutual_funds_vinay.json") +
                                   load("mutual_funds_harsh.json") +
                                   load("mutual_funds_anusha.json") +
                                   load("mom_mutual_funds.json"))
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
                            def _iso(s):
                                try:
                                    return datetime.datetime.strptime(s.strip(), "%d-%b-%Y").strftime("%Y-%m-%d")
                                except ValueError:
                                    return s.strip()

                            mf_rows = []
                            for isin in all_isins:
                                if isin in amfi:
                                    d = amfi[isin]
                                    mf_rows.append({"isin": isin, "nav": d["nav"],
                                                    "nav_date": _iso(d["date"]), "amfi_name": d["name"],
                                                    "fetched_at": datetime.datetime.utcnow().isoformat()})
                            if mf_rows:
                                service_upsert("mf_navs", mf_rows, conflict_col="isin")
                                _updated += len(mf_rows)
                        except Exception:
                            pass

                    # Watchlist
                    holdings_wl = load("watchlist.json")
                    wl_errors = []
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
                                for item, t in zip(group, tickers):
                                    sym = item["symbol"].upper()
                                    try:
                                        closes = raw[t]["Close"].dropna()
                                        highs  = raw[t]["High"].dropna()
                                        lows   = raw[t]["Low"].dropna()
                                        if len(closes) > 0:
                                            wl_rows.append({
                                                "symbol":        sym,
                                                "last_close":    round(float(closes.iloc[-1]), 4),
                                                "current_price": round(float(closes.iloc[-1]), 4),
                                                "high_52w":      round(float(highs.max()), 4),
                                                "low_52w":       round(float(lows.min()), 4),
                                                "fetched_at":    datetime.datetime.utcnow().isoformat(),
                                            })
                                        else:
                                            wl_errors.append(f"{sym}: no data returned (ticker={t})")
                                    except Exception as e:
                                        wl_errors.append(f"{sym}: {e}")
                            except Exception as e:
                                wl_errors.append(f"Region {region} download failed: {e}")
                        if wl_rows:
                            deduped = list({r["symbol"]: r for r in wl_rows}.values())
                            service_upsert("watchlist_prices", deduped, conflict_col="symbol")
                            _updated += len(deduped)
                    st.session_state["_wl_errors"] = wl_errors

                    # ── History snapshot check ─────────────────────────
                    # Always check when manually refreshed — no market-hours
                    # restriction (user is making an explicit call to catch up)
                    _today_str = datetime.datetime.now(_IST_TZ).date().isoformat()
                    _existing  = fetch_one("portfolio_history", "date", _today_str)
                    if _existing:
                        _hist_status = ("info",
                            f"📅 History for {_today_str} already recorded.")
                    else:
                        try:
                            _frow, _ = _record_history_snapshot()
                            from utils.fmt import ind_num
                            _hist_status = ("success",
                                f"📅 History snapshot saved for {_today_str}  "
                                f"(Total CV: {ind_num(_frow['total_cv'])})")
                        except Exception as _he:
                            _hist_status = ("warning",
                                f"📅 History snapshot failed: {_he}")
                    st.session_state["_hist_status"] = _hist_status

                    st.success(f"✅ Prices updated ({_updated} securities).")
                    st.rerun()
                except Exception as e:
                    st.error(f"Refresh failed: {e}")
        if st.session_state.get("_wl_errors"):
            for err in st.session_state["_wl_errors"]:
                st.warning(f"⚠️ WL: {err}")
        _hs = st.session_state.get("_hist_status")
        if _hs:
            typ, msg = _hs
            if typ == "success": st.success(msg)
            elif typ == "warning": st.warning(msg)
            else: st.info(msg)
        st.markdown("---")
