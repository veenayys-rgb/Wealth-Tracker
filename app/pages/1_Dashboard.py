"""Dashboard — Full Net Worth Summary + Refresh Prices button."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar, render_index_bar
import pandas as pd
from utils.db     import fetch, get_forex, fetch_latest_ts
from utils.config import load
from utils.fmt    import ind_num, pct, metric_card, utc_to_ist

st.set_page_config(page_title="Dashboard | Wealth Tracker", page_icon="📊", layout="wide")
st.title("📊 Dashboard")
render_sidebar()
render_index_bar()

# ── Forex + Market Indices ────────────────────────────────────────────────────
forex   = get_forex()
aed     = forex.get("AED_INR", 0)
usd     = forex.get("USD_INR", 0)
nifty   = forex.get("NIFTY50", 0)
sensex  = forex.get("SENSEX",  0)

_parts = [f"AED/INR: {aed:.4f}", f"USD/INR: {usd:.4f}"]
if nifty  > 0: _parts.append(f"Nifty 50: {nifty:,.2f}")
if sensex > 0: _parts.append(f"Sensex: {sensex:,.2f}")
st.caption("  |  ".join(_parts))


# ── Compute all asset values ──────────────────────────────────────────────────
_FAMILY = {"Vinay", "Harsh", "Anusha"}

def eq_india_totals() -> tuple:
    prices = {r["symbol"]: float(r["price"]) for r in fetch("equity_india_prices")}
    inv = cv = 0.0
    for h in load("equity_india.json"):
        if h.get("owner") and h["owner"] not in _FAMILY:
            continue
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
    total = sum(float(b.get("balance", 0)) for b in load("bank_india.json")
                if b.get("owner", "Vinay") in _FAMILY)
    for b in load("bank_uae.json"):
        curr = b.get("currency", "AED")
        rate = usd if curr == "USD" else aed
        total += float(b.get("balance_aed", 0)) * rate
    return round(total, 2)


def _fx(curr):
    if curr == "AED": return aed
    if curr == "USD": return usd
    return 1.0


def fd_total_inr() -> float:
    total = 0.0
    for fd in load("fixed_deposits.json"):
        if fd.get("owner") and fd["owner"] not in _FAMILY:
            continue
        amt  = float(fd.get("amount", 0))
        curr = fd.get("currency", "INR")
        total += amt * _fx(curr)
    return round(total, 2)


def insurance_surrender_inr() -> float:
    total = 0.0
    for p in load("insurance.json"):
        sv   = float(p.get("surrender_value", 0))
        curr = p.get("currency", "INR")
        total += sv * _fx(curr)
    return round(total, 2)


def day_gl_family() -> tuple[float, float]:
    """Today's G/L for Family (Vinay+Harsh+Anusha) across equity+intl+MF.
    Returns (day_gl, invest_cv) where invest_cv is eq+intl+MF current value."""
    day_gl = 0.0
    inv_cv = 0.0

    # India equity
    eq_rows = {r["symbol"]: r for r in fetch("equity_india_prices")}
    for h in load("equity_india.json"):
        if h.get("owner") and h["owner"] not in _FAMILY:
            continue
        sym   = h["symbol"].upper()
        qty   = float(h.get("qty", 0))
        r     = eq_rows.get(sym, {})
        price = float(r["price"])      if r.get("price")      else 0.0
        prev  = float(r["prev_price"]) if r.get("prev_price") else 0.0
        inv_cv += qty * price if price > 0 else 0.0
        if price > 0 and prev > 0:
            day_gl += (price - prev) * qty

    # International equity
    intl_rows = {r["symbol"]: r for r in fetch("equity_international_prices")}
    for h in load("equity_international.json"):
        sym   = h["symbol"].upper()
        qty   = float(h.get("qty", 0))
        curr  = h.get("currency", "USD")
        rate  = aed if curr == "AED" else usd
        r     = intl_rows.get(sym, {})
        price = float(r["price"])      if r.get("price")      else 0.0
        prev  = float(r["prev_price"]) if r.get("prev_price") else 0.0
        inv_cv += qty * price * rate if price > 0 else 0.0
        if price > 0 and prev > 0:
            day_gl += (price - prev) * qty * rate

    # Mutual Funds
    nav_rows = {r["isin"]: r for r in fetch("mf_navs")}
    for fname in ["mutual_funds_vinay.json", "mutual_funds_harsh.json", "mutual_funds_anusha.json"]:
        for h in load(fname):
            isin  = h.get("isin", "").upper()
            units = float(h.get("units", 0))
            n     = nav_rows.get(isin, {})
            nav   = float(n["nav"])      if n.get("nav")      else 0.0
            prev  = float(n["prev_nav"]) if n.get("prev_nav") else 0.0
            inv_cv += units * nav if nav > 0 else 0.0
            if nav > 0 and prev > 0:
                day_gl += (nav - prev) * units

    return round(day_gl, 2), round(inv_cv, 2)


eq_inv,  eq_cv    = eq_india_totals()
mf_v_inv, mf_v_cv = mf_totals("mutual_funds_vinay.json")
mf_h_inv, mf_h_cv = mf_totals("mutual_funds_harsh.json")
mf_a_inv, mf_a_cv = mf_totals("mutual_funds_anusha.json")
intl_inv, intl_cv  = intl_totals()
bank_cv            = bank_total_inr()
fd_cv              = fd_total_inr()
ins_cv             = insurance_surrender_inr()
day_gl, invest_cv  = day_gl_family()

total_inv = eq_inv + mf_v_inv + mf_h_inv + mf_a_inv + intl_inv
total_cv  = eq_cv  + mf_v_cv  + mf_h_cv  + mf_a_cv  + intl_cv + bank_cv + fd_cv + ins_cv
gain      = total_cv - total_inv
ret_pct   = (gain / total_inv * 100) if total_inv > 0 else 0
day_pct   = (day_gl / invest_cv * 100) if invest_cv > 0 else 0

# ── Summary cards ─────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.markdown(metric_card("Total Net Worth",  ind_num(total_cv)),  unsafe_allow_html=True)
c2.markdown(metric_card("Total Invested",   ind_num(total_inv)), unsafe_allow_html=True)
c3.markdown(metric_card("Gain / Loss",      ind_num(gain), delta=pct(ret_pct)), unsafe_allow_html=True)
c4.markdown(metric_card("Today's G/L",      ind_num(day_gl), delta=pct(day_pct)), unsafe_allow_html=True)

st.divider()

# ── Asset breakdown table ─────────────────────────────────────────────────────
st.subheader("Net Worth Breakdown")

mf_inv = mf_v_inv + mf_h_inv + mf_a_inv
mf_cv  = mf_v_cv  + mf_h_cv  + mf_a_cv

asset_rows = [
    ("India Equity",        eq_inv,   eq_cv),
    ("Mutual Funds",        mf_inv,   mf_cv),
    ("International Equity", intl_inv, intl_cv),
    ("Bank Accounts",       0,        bank_cv),
    ("Fixed Deposits",      0,        fd_cv),
    ("Insurance",           0,        ins_cv),
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

st.divider()

# ── Last Data Refresh status ──────────────────────────────────────────────────
with st.expander("🔄 Last Data Refresh", expanded=False):
    import datetime as _dt

    _today = _dt.date.today()
    _IST   = _dt.timezone(_dt.timedelta(hours=5, minutes=30))

    def _status(ts_str: str | None) -> str:
        if not ts_str:
            return "❌  Never"
        try:
            dt  = _dt.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_dt.timezone.utc)
            days = (_today - dt.astimezone(_IST).date()).days
            if days == 0:   return "✅  Today"
            if days == 1:   return "⚠️  Yesterday"
            if days <= 4:   return f"⚠️  {days} days ago"
            return          f"❌  {days} days ago"
        except Exception:
            return "❌  Unknown"

    _feeds = [
        ("Forex & Indices",       "forex_rates"),
        ("MF NAVs",               "mf_navs"),
        ("India Equity",          "equity_india_prices"),
        ("International Equity",  "equity_international_prices"),
        ("Watchlist",             "watchlist_prices"),
    ]

    _rows = []
    for label, table in _feeds:
        try:
            ts = fetch_latest_ts(table)
        except Exception:
            ts = None
        _rows.append({
            "Feed":          label,
            "Last Updated":  utc_to_ist(ts) if ts else "—",
            "Status":        _status(ts),
        })

    st.dataframe(
        pd.DataFrame(_rows),
        use_container_width=True,
        hide_index=True,
    )
