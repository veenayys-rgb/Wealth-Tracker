"""Shared sidebar — Refresh Prices button + page-scoped refresh helpers."""
import datetime, time, ssl, urllib.request
import streamlit as st
import yfinance as yf
from utils.db     import service_upsert, fetch, fetch_one
from utils.config import load

SUFFIX   = {"India": ".NS", "UAE": ".AD", "US": "", "UK": ".L", "Other": ""}
_IST_TZ  = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
_FAMILY  = {"Vinay", "Harsh", "Anusha"}


@st.cache_data(ttl=300)
def _fetch_index_levels() -> dict:
    """Fetch Nifty50 and Sensex with prev close. Cached 5 min."""
    ssl._create_default_https_context = ssl._create_unverified_context
    result = {}
    for name, ticker in [("NIFTY50", "^NSEI"), ("SENSEX", "^BSESN")]:
        try:
            closes = yf.Ticker(ticker).history(period="5d")["Close"].dropna()
            if len(closes) >= 2:
                curr = round(float(closes.iloc[-1]), 2)
                prev = round(float(closes.iloc[-2]), 2)
                result[name] = {"current": curr, "change": round(curr - prev, 2),
                                "change_pct": round((curr - prev) / prev * 100, 2)}
            elif len(closes) == 1:
                result[name] = {"current": round(float(closes.iloc[-1]), 2),
                                "change": None, "change_pct": None}
            else:
                result[name] = None
        except Exception:
            result[name] = None
    return result


def render_index_bar():
    """Render Nifty50/Sensex bar. Falls back to forex_rates table if yfinance unavailable."""
    levels = _fetch_index_levels()

    # Fallback to stored forex_rates if yfinance returned nothing
    if any(levels.get(k) is None for k in ["NIFTY50", "SENSEX"]):
        try:
            stored = {r["pair"]: r for r in fetch("forex_rates")}
            for name in ["NIFTY50", "SENSEX"]:
                if levels.get(name) is None and name in stored:
                    from utils.fmt import utc_to_ist
                    levels[name] = {
                        "current":     round(float(stored[name]["rate"]), 2),
                        "change":      None,
                        "change_pct":  None,
                        "fallback_ts": utc_to_ist(stored[name].get("fetched_at")),
                    }
        except Exception:
            pass

    now_str = datetime.datetime.now(_IST_TZ).strftime("%d-%b-%Y  %I:%M %p IST")

    def _block(label, data):
        if data is None:
            return (f'<div class="idx-block"><span class="idx-lbl">{label}</span>'
                    f'<span class="idx-lvl">—</span></div>')
        lvl = f"{data['current']:,.0f}"
        if data.get("change") is not None:
            ch, pct = data["change"], data["change_pct"]
            sign  = "+" if ch >= 0 else ""
            color = "#1A7A4A" if ch >= 0 else "#C0392B"
            icon  = "ti-trending-up" if ch >= 0 else "ti-trending-down"
            ch_html = (f'<span class="idx-chg" style="color:{color}">'
                       f'<i class="ti {icon}" aria-hidden="true"></i>'
                       f' {sign}{ch:,.0f} pts ({sign}{pct:.2f}%)</span>')
        else:
            ch_html = '<span class="idx-nodata">no change data</span>'
        return (f'<div class="idx-block"><span class="idx-lbl">{label}</span>'
                f'<span class="idx-lvl">{lvl}</span>{ch_html}</div>')

    # Timestamp: prefer fallback_ts if both are fallbacks, else current fetch time
    fb_ts = None
    for k in ["NIFTY50", "SENSEX"]:
        d = levels.get(k) or {}
        if d.get("fallback_ts"):
            fb_ts = d["fallback_ts"]
            break
    ts_label = f"Last fetched: {fb_ts}" if fb_ts else now_str

    n_html = _block("NIFTY 50", levels.get("NIFTY50"))
    s_html = _block("SENSEX",   levels.get("SENSEX"))

    st.markdown(f"""
<style>
.idx-bar{{background:var(--color-background-primary);border:0.5px solid var(--color-border-tertiary);
border-radius:8px;padding:0.65rem 1.25rem;display:flex;align-items:center;gap:2rem;
flex-wrap:wrap;margin-bottom:0.75rem;}}
.idx-block{{display:flex;align-items:baseline;gap:0.6rem;}}
.idx-lbl{{font-size:13px;font-weight:500;color:var(--color-text-secondary);}}
.idx-lvl{{font-size:20px;font-weight:500;color:var(--color-text-primary);}}
.idx-chg{{font-size:14px;font-weight:500;}}
.idx-chg i{{font-size:15px;vertical-align:-2px;}}
.idx-nodata{{font-size:13px;color:var(--color-text-tertiary);}}
.idx-div{{width:0.5px;height:28px;background:var(--color-border-tertiary);flex-shrink:0;}}
.idx-ts{{margin-left:auto;font-size:11px;color:var(--color-text-tertiary);white-space:nowrap;}}
</style>
<div class="idx-bar">
  {n_html}
  <div class="idx-div"></div>
  {s_html}
  <div class="idx-ts">{ts_label}</div>
</div>""", unsafe_allow_html=True)


def _market_closed() -> bool:
    """True if NSE market is closed — before 8 AM IST, after 3:30 PM IST, or weekend."""
    now = datetime.datetime.now(_IST_TZ)
    if now.weekday() >= 5:          # Saturday / Sunday
        return True
    open_time  = now.replace(hour=8,  minute=0,  second=0, microsecond=0)
    close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return now < open_time or now >= close_time


def record_history_snapshot() -> tuple[dict, dict]:
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


def _apply_prev_price(rows: list[dict], table: str) -> list[dict]:
    """Date-guard: roll current → prev_price only on a new trading day."""
    today = datetime.datetime.now(_IST_TZ).date().isoformat()
    try:
        existing = {r["symbol"]: r for r in fetch(table)}
    except Exception:
        existing = {}
    for r in rows:
        ex      = existing.get(r["symbol"], {})
        ex_date = str(ex.get("prev_price_date") or "")
        ex_px   = float(ex["price"]) if ex.get("price") else 0.0
        if ex_date != today and ex_px > 0:
            r["prev_price"]      = ex_px
            r["prev_price_date"] = today
        else:
            r["prev_price"]      = float(ex["prev_price"]) if ex.get("prev_price") else None
            r["prev_price_date"] = ex_date or None
    return rows


def apply_prev_nav(rows: list[dict]) -> list[dict]:
    """Date-guard for MF NAVs: roll nav → prev_nav only when nav_date changes."""
    try:
        existing = {r["isin"]: r for r in fetch("mf_navs")}
    except Exception:
        existing = {}
    for r in rows:
        ex           = existing.get(r["isin"], {})
        ex_nav_date  = str(ex.get("nav_date")  or "")
        new_nav_date = str(r.get("nav_date")   or "")
        ex_nav       = float(ex["nav"]) if ex.get("nav") else 0.0
        if ex_nav_date != new_nav_date and ex_nav > 0:
            r["prev_nav"]      = ex_nav
            r["prev_nav_date"] = ex_nav_date or None
        else:
            r["prev_nav"]      = float(ex["prev_nav"]) if ex.get("prev_nav") else None
            r["prev_nav_date"] = str(ex.get("prev_nav_date") or "") or None
    return rows


_INTL_SUFFIX = {"UAE": ".AD", "US": "", "UK": ".L", "Other": ""}


def refresh_india_equity_prices() -> tuple[int, int]:
    """Fetch India equity prices (NSE batch + fallback). Returns (saved, total)."""
    _FILES = ["equity_india_vinay.json", "equity_india_harsh.json",
              "equity_india_anusha.json", "mom_equity_india.json"]
    all_h = []
    for f in _FILES:
        all_h.extend(load(f))
    if not all_h:
        return 0, 0
    syms = list({h["symbol"].upper() for h in all_h if h.get("symbol", "").strip()})
    ssl._create_default_https_context = ssl._create_unverified_context
    eq_rows, nse_miss = [], []
    nse_tickers = [f"{s}.NS" for s in syms]
    try:
        raw   = yf.download(nse_tickers, period="5d", auto_adjust=True,
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
        nse_miss = syms
    for s in nse_miss:
        for suffix in [".NS", ".BO"]:
            try:
                info  = yf.Ticker(f"{s}{suffix}").fast_info
                p     = getattr(info, "last_price", None)
                if p and float(p) > 0:
                    eq_rows.append({"symbol": s, "price": round(float(p), 4),
                                    "fetched_at": datetime.datetime.utcnow().isoformat()})
                    break
            except Exception:
                pass
            time.sleep(0.2)
        time.sleep(0.3)
    rows = list({r["symbol"]: r for r in eq_rows}.values())
    rows = _apply_prev_price(rows, "equity_india_prices")
    service_upsert("equity_india_prices", rows, conflict_col="symbol")
    return len(rows), len(syms)


def refresh_intl_equity_prices() -> tuple[int, int]:
    """Fetch international equity prices. Returns (saved, total)."""
    _FILES = ["equity_intl_vinay.json", "equity_intl_harsh.json", "equity_intl_anusha.json"]
    all_h = []
    for f in _FILES:
        all_h.extend(load(f))
    if not all_h:
        return 0, 0
    total = len({h["symbol"].upper() for h in all_h if h.get("symbol")})
    by_region: dict = {}
    for h in all_h:
        by_region.setdefault(h.get("region", "Other"), []).append(h)
    rows = []
    for region, items in by_region.items():
        suffix  = _INTL_SUFFIX.get(region, "")
        tickers = [f"{h['symbol'].upper()}{suffix}" for h in items]
        try:
            raw   = yf.download(tickers, period="5d", auto_adjust=True,
                                progress=False, group_by="ticker", threads=True)
            multi = len(tickers) > 1
            for h, t in zip(items, tickers):
                sym = h["symbol"].upper()
                try:
                    closes = raw[t]["Close"].dropna() if multi else raw["Close"].dropna()
                    price  = round(float(closes.iloc[-1]), 4) if len(closes) > 0 else 0
                    if price > 0:
                        rows.append({"symbol": sym, "region": region,
                                     "currency": h.get("currency", "USD"),
                                     "price": price,
                                     "fetched_at": datetime.datetime.utcnow().isoformat()})
                except Exception:
                    pass
        except Exception:
            pass
    rows = list({r["symbol"]: r for r in rows}.values())
    rows = _apply_prev_price(rows, "equity_international_prices")
    service_upsert("equity_international_prices", rows, conflict_col="symbol")
    return len(rows), total


def refresh_watchlist_prices() -> tuple[int, int, list[str]]:
    """Fetch 52-week data for all watchlist symbols. Returns (saved, total, errors)."""
    items = load("watchlist.json")
    if not items:
        return 0, 0, []
    total = len(items)
    by_region: dict = {}
    for item in items:
        by_region.setdefault(item.get("region", "Other"), []).append(item)
    wl_rows, errors = [], []
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
                    else:
                        errors.append(f"{sym}: no data returned")
                except Exception as e:
                    errors.append(f"{sym}: {e}")
        except Exception as e:
            errors.append(f"Region {region}: {e}")
    if wl_rows:
        deduped = list({r["symbol"]: r for r in wl_rows}.values())
        service_upsert("watchlist_prices", deduped, conflict_col="symbol")
    return len(wl_rows), total, errors


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

                    # India Equity — NSE batch (5d), then individual NSE/BSE fallback
                    holdings_eq = load("equity_india.json")
                    if holdings_eq:
                        syms = list({h["symbol"].upper() for h in holdings_eq if h.get("symbol","").strip()})
                        ssl._create_default_https_context = ssl._create_unverified_context
                        eq_rows  = []
                        nse_miss = []

                        # ── NSE batch (5d gives more headroom than 2d) ─────────
                        nse_tickers = [f"{s}.NS" for s in syms]
                        try:
                            raw   = yf.download(nse_tickers, period="5d", auto_adjust=True,
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
                            nse_miss = syms   # full batch failed — retry all individually

                        # ── Individual fallback: NSE fast_info → BSE fast_info ─
                        for s in nse_miss:
                            price = 0.0
                            for suffix in [".NS", ".BO"]:
                                try:
                                    info  = yf.Ticker(f"{s}{suffix}").fast_info
                                    p     = getattr(info, "last_price", None)
                                    if p and float(p) > 0:
                                        price = round(float(p), 4)
                                        break
                                except Exception:
                                    pass
                                time.sleep(0.2)
                            if price > 0:
                                eq_rows.append({"symbol": s, "price": price,
                                                "fetched_at": datetime.datetime.utcnow().isoformat()})
                            time.sleep(0.3)

                        if eq_rows:
                            deduped = list({r["symbol"]: r for r in eq_rows}.values())
                            deduped = _apply_prev_price(deduped, "equity_india_prices")
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
                            # AMFI NAVAll.txt format (8 cols as of Aug 2025):
                            # Code; ISIN Growth; ISIN Div-Reinv; Name; Plan; Option; NAV; Date
                            amfi  = {}
                            for line in lines:
                                parts = line.strip().split(";")
                                if len(parts) < 8:
                                    continue
                                try:
                                    nav  = float(parts[6].strip())
                                    for isin in [parts[1].strip().upper(), parts[2].strip().upper()]:
                                        if isin and isin != "-":
                                            amfi[isin] = {"nav": nav, "name": parts[3].strip(),
                                                          "date": parts[7].strip()}
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
                                mf_rows = apply_prev_nav(mf_rows)
                                service_upsert("mf_navs", mf_rows, conflict_col="isin")
                                _updated += len(mf_rows)
                        except Exception:
                            pass

                    # Watchlist
                    _wl_saved, _, _wl_errors = refresh_watchlist_prices()
                    _updated += _wl_saved
                    st.session_state["_wl_errors"] = _wl_errors

                    # ── History snapshot — always record on manual refresh ──
                    _today_str = datetime.datetime.now(_IST_TZ).date().isoformat()
                    try:
                        _frow, _ = record_history_snapshot()
                        from utils.fmt import ind_num
                        _warn = ("  ⚠️ Market may still be open — prices are intra-day."
                                 if not _market_closed() else "")
                        _hist_status = ("success",
                            f"📅 History snapshot saved for {_today_str}  "
                            f"(Total CV: {ind_num(_frow['total_cv'])}){_warn}")
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

