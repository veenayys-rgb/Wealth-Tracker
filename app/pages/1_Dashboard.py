"""Dashboard — Full Net Worth Summary + Refresh Prices button."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import datetime, time, urllib.request, ssl
import yfinance as yf
from utils.db     import fetch, get_forex, service_upsert
from utils.config import load
from utils.fmt    import ind_num, pct, metric_card

st.set_page_config(page_title="Dashboard | Wealth Tracker", page_icon="📊", layout="wide")
st.title("📊 Dashboard")

# ── Refresh Prices button ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    if st.button("🔄 Refresh Prices", use_container_width=True, type="primary"):
        with st.spinner("Fetching latest prices…"):
            try:
                _updated = 0

                # Forex
                PAIRS = [("AED_INR", "AEDINR=X"), ("USD_INR", "USDINR=X")]
                fx_rows = []
                for pair, ticker in PAIRS:
                    try:
                        info = yf.Ticker(ticker).fast_info
                        rate = getattr(info, "last_price", None)
                        if rate and float(rate) > 0:
                            fx_rows.append({"pair": pair, "rate": round(float(rate), 6),
                                            "fetched_at": datetime.datetime.utcnow().isoformat()})
                    except Exception:
                        pass
                    time.sleep(0.3)
                if fx_rows:
                    service_upsert("forex_rates", fx_rows, conflict_col="pair")

                # India Equity
                holdings_eq = load("equity_india.json")
                if holdings_eq:
                    syms = list({h["symbol"].upper() for h in holdings_eq})
                    tickers = [f"{s}.NS" for s in syms]
                    try:
                        ssl._create_default_https_context = ssl._create_unverified_context
                        raw = yf.download(tickers, period="2d", auto_adjust=True,
                                          progress=False, group_by="ticker", threads=True)
                        multi = len(tickers) > 1
                        eq_rows = []
                        for s, t in zip(syms, tickers):
                            try:
                                close = raw[t]["Close"].dropna() if multi else raw["Close"].dropna()
                                price = round(float(close.iloc[-1]), 4) if len(close) > 0 else 0
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
                all_isins = {h.get("isin","").upper() for h in holdings_mf if h.get("isin")}
                if all_isins:
                    try:
                        ctx = ssl.create_default_context()
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
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
                                name = parts[3].strip()
                                date = parts[5].strip()
                                for isin in [parts[1].strip().upper(), parts[2].strip().upper()]:
                                    if isin:
                                        amfi[isin] = {"nav": nav, "name": name, "date": date}
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

                st.success(f"✅ Prices updated ({_updated} securities). Reload the page to see latest values.")
            except Exception as e:
                st.error(f"Refresh failed: {e}")
    st.markdown("---")

# ── Forex ─────────────────────────────────────────────────────────────────────
forex = get_forex()
aed   = forex.get("AED_INR", 0)
usd   = forex.get("USD_INR", 0)
st.caption(f"AED/INR: {aed:.4f}  |  USD/INR: {usd:.4f}")


# ── Compute all asset values ──────────────────────────────────────────────────
def eq_india_totals() -> tuple:
    prices = {r["symbol"]: float(r["price"]) for r in fetch("equity_india_prices")}
    inv = cv = 0.0
    for h in load("equity_india.json"):
        qty   = float(h.get("qty", 0))
        cost  = float(h.get("avg_cost", 0))
        price = prices.get(h["symbol"].upper(), 0)
        inv  += qty * cost
        cv   += qty * price if price > 0 else qty * cost
    return round(inv, 2), round(cv, 2)


def mf_totals(fname: str) -> tuple:
    navs = {r["isin"]: float(r["nav"]) for r in fetch("mf_navs")}
    inv = cv = 0.0
    for h in load(fname):
        units = float(h.get("units", 0))
        anav  = float(h.get("avg_nav", 0))
        nav   = navs.get(h.get("isin", "").upper(), 0)
        inv  += units * anav
        cv   += units * nav if nav > 0 else units * anav
    return round(inv, 2), round(cv, 2)


def intl_totals() -> tuple:
    prices = {r["symbol"]: float(r["price"]) for r in fetch("equity_international_prices")}
    inv = cv = 0.0
    for h in load("equity_international.json"):
        sym   = h["symbol"].upper()
        qty   = float(h.get("qty", 0))
        cost  = float(h.get("avg_cost", 0))
        curr  = h.get("currency", "USD")
        rate  = aed if curr == "AED" else usd
        price = prices.get(sym, 0)
        inv  += qty * cost  * rate
        cv   += qty * price * rate if price > 0 else qty * cost * rate
    return round(inv, 2), round(cv, 2)


def bank_total_inr() -> float:
    total  = sum(float(b.get("balance", 0)) for b in load("bank_india.json"))
    total += sum(float(b.get("balance_aed", 0)) * aed for b in load("bank_uae.json"))
    return round(total, 2)


def fd_total_inr() -> float:
    total = 0.0
    for fd in load("fixed_deposits.json"):
        amt  = float(fd.get("amount", 0))
        curr = fd.get("currency", "INR")
        total += amt * aed if curr == "AED" else amt
    return round(total, 2)


def insurance_surrender_inr() -> float:
    total = 0.0
    for p in load("insurance.json"):
        sv   = float(p.get("surrender_value", 0))
        curr = p.get("currency", "INR")
        total += sv * aed if curr == "AED" else sv
    return round(total, 2)


eq_inv,  eq_cv    = eq_india_totals()
mf_v_inv, mf_v_cv = mf_totals("mutual_funds_vinay.json")
mf_h_inv, mf_h_cv = mf_totals("mutual_funds_harsh.json")
mf_a_inv, mf_a_cv = mf_totals("mutual_funds_anusha.json")
intl_inv, intl_cv  = intl_totals()
bank_cv            = bank_total_inr()
fd_cv              = fd_total_inr()
ins_cv             = insurance_surrender_inr()

total_inv = eq_inv + mf_v_inv + mf_h_inv + mf_a_inv + intl_inv
total_cv  = eq_cv  + mf_v_cv  + mf_h_cv  + mf_a_cv  + intl_cv + bank_cv + fd_cv + ins_cv
gain      = total_cv - total_inv
ret_pct   = (gain / total_inv * 100) if total_inv > 0 else 0

# ── Summary cards ─────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
c1.markdown(metric_card("Total Net Worth",  ind_num(total_cv)),  unsafe_allow_html=True)
c2.markdown(metric_card("Total Invested",   ind_num(total_inv)), unsafe_allow_html=True)
c3.markdown(metric_card("Gain / Loss",      ind_num(gain), delta=pct(ret_pct)), unsafe_allow_html=True)

st.divider()

# ── Asset breakdown table ─────────────────────────────────────────────────────
st.subheader("Net Worth Breakdown")

asset_rows = [
    ("India Equity",   eq_inv,   eq_cv),
    ("MF — Vinay",     mf_v_inv, mf_v_cv),
    ("MF — Harsh",     mf_h_inv, mf_h_cv),
    ("MF — Anusha",    mf_a_inv, mf_a_cv),
    ("International",  intl_inv, intl_cv),
    ("Bank Accounts",  0,        bank_cv),
    ("Fixed Deposits", 0,        fd_cv),
    ("Insurance",      0,        ins_cv),
]

data = []
for name, inv, cv in asset_rows:
    gl    = cv - inv
    ret   = (gl / inv * 100) if inv > 0 else 0
    alloc = (cv / total_cv * 100) if total_cv > 0 else 0
    data.append({
        "Asset Class":   name,
        "Invested":      ind_num(inv) if inv > 0 else "—",
        "Current Value": ind_num(cv),
        "Gain/Loss":     ind_num(gl) if inv > 0 else "—",
        "Return %":      f"{ret:+.2f}%" if inv > 0 else "—",
        "Allocation %":  alloc,
        "_inv": inv, "_cv": cv, "_gl": gl,
    })

df = pd.DataFrame(data)
st.dataframe(
    df.drop(columns=["_inv","_cv","_gl"]).style.format({"Allocation %": "{:.2f}%"}),
    use_container_width=True,
    hide_index=True,
)

st.caption("Insurance = Surrender Value  |  Bank/FD/UAE shown as INR equivalent")
