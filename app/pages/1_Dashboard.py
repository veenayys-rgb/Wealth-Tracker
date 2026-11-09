"""Dashboard — Full Net Worth Summary + Refresh Prices button."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import datetime as _dt
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


def insurance_invested_inr() -> float:
    total = 0.0
    for p in load("insurance.json"):
        paid = float(p.get("premium_paid_ytd", 0))
        curr = p.get("currency", "INR")
        total += paid * _fx(curr)
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
ins_inv            = insurance_invested_inr()

mf_inv    = mf_v_inv + mf_h_inv + mf_a_inv
mf_cv     = mf_v_cv  + mf_h_cv  + mf_a_cv

# total_inv includes bank+fd at face value so the Invested column sums correctly
total_inv = eq_inv + mf_inv + intl_inv + bank_cv + fd_cv + ins_inv
total_cv  = eq_cv  + mf_cv  + intl_cv  + bank_cv + fd_cv + ins_cv
gain      = total_cv - total_inv
ret_pct   = (gain / total_inv * 100) if total_inv > 0 else 0

# ── Prev-day snapshot (for comparison) ───────────────────────────────────────
_IST_TZ = _dt.timezone(_dt.timedelta(hours=5, minutes=30))

def _trading_date(ts: str) -> _dt.date:
    dt = _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    ist = dt.astimezone(_IST_TZ)
    d = ist.date()
    if ist.hour < 9:
        d -= _dt.timedelta(days=1)
        while d.weekday() >= 5:
            d -= _dt.timedelta(days=1)
    return d

@st.cache_data(ttl=300)
def _load_prev_snap():
    today = _trading_date(_dt.datetime.now(_dt.timezone.utc).isoformat())
    snaps = fetch("dashboard_snapshots")
    earlier = [s for s in snaps if _trading_date(s["recorded_at"]) < today]
    return max(earlier, key=lambda s: s["recorded_at"]) if earlier else None

_SNAP_OWNERS = ["vinay", "harsh", "anusha"]

def _snap_sum(snap, cats):
    return sum(float(snap.get(f"{o}_{c}", 0) or 0) for o in _SNAP_OWNERS for c in cats)

prev_snap = _load_prev_snap()

_ASSET_SNAP_CATS = {
    "India Equity":          ["india_eq"],
    "Mutual Funds":          ["mf"],
    "International Equity":  ["intl_eq"],
    "Bank Accounts":         ["bank_india", "bank_uae"],
    "Fixed Deposits":        ["fd"],
    "Insurance":             ["insurance"],
}

prev_cv_map: dict = {}
prev_total_cv: float | None = None
if prev_snap:
    prev_cv_map  = {name: _snap_sum(prev_snap, cats) for name, cats in _ASSET_SNAP_CATS.items()}
    prev_total_cv = sum(prev_cv_map.values())
    prev_total_inv = sum(
        float(prev_snap.get(f"{o}_{c}", 0) or 0)
        for o in _SNAP_OWNERS
        for c in ["india_eq", "mf", "intl_eq"]
    )
    prev_gain = prev_total_cv - prev_total_inv

# ── Summary cards ─────────────────────────────────────────────────────────────
def _tile(label: str, val_str: str, sub: str | None,
          curr: float, prev: float | None) -> str:
    sub_h = (f'<div style="font-size:.75em;color:#888;margin-top:1px">{sub}</div>') if sub else ""
    if prev is not None and prev > 0:
        chg   = curr - prev
        color = "green" if chg >= 0 else "red"
        cpct  = abs(chg / prev * 100)
        bot = (
            f'<div style="border-top:1px solid #ddd;margin-top:8px;padding-top:7px;'
            f'display:flex;gap:16px;flex-wrap:wrap">'
            f'<div><div style="font-size:.65em;color:#888">prev day close</div>'
            f'<div style="font-size:.8em;color:#6b4fa0">{ind_num(prev)}</div></div>'
            f'<div><div style="font-size:.65em;color:#888">change</div>'
            f'<div style="font-size:.85em;font-weight:600;color:{color}">'
            f'{ind_num(abs(chg), decimals=0)} ({cpct:.2f}%)</div></div>'
            f'</div>'
        )
    else:
        bot = ""
    return (
        f'<div class="wt-tile" style="background:#f0f2f6;border-radius:8px;padding:16px 20px">'
        f'<div class="wt-tile-label" style="font-size:.8em;color:#555;margin-bottom:4px">{label}</div>'
        f'<div class="wt-tile-val" style="font-size:1.35em;font-weight:700">{val_str}</div>'
        f'{sub_h}{bot}</div>'
    )

c1, c2, c3 = st.columns(3)
c1.markdown(_tile("Total Net Worth", ind_num(total_cv), None,
                  total_cv, prev_total_cv), unsafe_allow_html=True)
c2.markdown(_tile("Total Invested",  ind_num(total_inv), None,
                  total_inv,
                  prev_total_inv if prev_snap else None), unsafe_allow_html=True)
c3.markdown(_tile("Gain / Loss", ind_num(gain), f"{ret_pct:.2f}% overall",
                  gain,
                  prev_gain if prev_snap else None), unsafe_allow_html=True)

st.divider()

# ── Asset breakdown table ─────────────────────────────────────────────────────
st.subheader("Net Worth Breakdown")

asset_rows = [
    ("India Equity",         eq_inv,   eq_cv),
    ("Mutual Funds",         mf_inv,   mf_cv),
    ("International Equity", intl_inv, intl_cv),
    ("Bank Accounts",        bank_cv,  bank_cv),
    ("Fixed Deposits",       fd_cv,    fd_cv),
    ("Insurance",            ins_inv,  ins_cv),
]


def _chg_cell(curr: float, prev: float | None) -> str:
    if prev is None or prev == 0:
        return "—"
    chg  = curr - prev
    cpct = abs(chg / prev * 100)
    color = "green" if chg >= 0 else "red"
    return (f'<span style="color:{color}">'
            f'{ind_num(abs(chg), decimals=0)} ({cpct:.2f}%)</span>')


def _build_table() -> str:
    show_prev = bool(prev_cv_map)

    # ── shared per-row computation ──────────────────────────────────────────
    computed = []
    for name, inv, cv in asset_rows:
        gl      = cv - inv
        ret     = (gl / inv * 100) if inv > 0 else None
        alloc   = (cv / total_cv * 100) if total_cv > 0 else 0
        has_gl  = inv > 0 and inv != cv
        prev_cv = prev_cv_map.get(name) if show_prev else None
        computed.append((name, inv, cv, gl, ret, alloc, has_gl, prev_cv))

    tot_ret = (gain / total_inv * 100) if total_inv > 0 else None

    # ── DESKTOP TABLE ───────────────────────────────────────────────────────
    th  = ("style='padding:7px 10px;text-align:right;font-size:.8em;"
           "color:#888;font-weight:500;border-bottom:1px solid #ddd;white-space:nowrap'")
    th_l = ("style='padding:7px 10px;text-align:left;font-size:.8em;"
            "color:#888;font-weight:500;border-bottom:1px solid #ddd'")
    th_p = ("style='padding:7px 10px;text-align:right;font-size:.8em;"
            "color:#6b4fa0;font-weight:500;border-bottom:1px solid #ddd;white-space:nowrap'")

    rows_html = ""
    for i, (name, inv, cv, gl, ret, alloc, has_gl, prev_cv) in enumerate(computed):
        bg   = "background:#f9f9f9" if i % 2 == 1 else ""
        td   = f"style='padding:7px 10px;text-align:right;border-bottom:.5px solid #eee;{bg}'"
        td_l = f"style='padding:7px 10px;text-align:left;font-weight:500;border-bottom:.5px solid #eee;{bg}'"
        td_p = f"style='padding:7px 10px;text-align:right;color:#6b4fa0;border-bottom:.5px solid #eee;{bg}'"
        gl_s = ind_num(gl) if has_gl else "—"
        ret_s = (f'<span style="color:{"green" if ret >= 0 else "red"}">{ret:.2f}%</span>'
                 if has_gl and ret is not None else "—")
        rows_html += (
            f"<tr>"
            f"<td {td_l}>{name}</td>"
            f"<td {td}>{ind_num(inv)}</td>"
            + (f"<td {td_p}>{ind_num(prev_cv) if prev_cv else '—'}</td>" if show_prev else "")
            + f"<td {td}>{ind_num(cv)}</td>"
            + (f"<td {td}>{_chg_cell(cv, prev_cv)}</td>" if show_prev else "")
            + f"<td {td}>{gl_s}</td>"
            f"<td {td}>{ret_s}</td>"
            f"<td {td}>{alloc:.2f}%</td>"
            f"</tr>"
        )

    tf   = "style='padding:8px 10px;text-align:right;font-weight:600;border-top:1px solid #ccc;background:#f0f2f6'"
    tf_l = "style='padding:8px 10px;text-align:left;font-weight:600;border-top:1px solid #ccc;background:#f0f2f6'"
    tf_p = "style='padding:8px 10px;text-align:right;font-weight:600;color:#6b4fa0;border-top:1px solid #ccc;background:#f0f2f6'"
    tot_ret_s = (f'<span style="color:{"green" if tot_ret >= 0 else "red"}">{tot_ret:.2f}%</span>'
                 if tot_ret is not None else "—")
    rows_html += (
        f"<tr>"
        f"<td {tf_l}>Total</td>"
        f"<td {tf}>{ind_num(total_inv)}</td>"
        + (f"<td {tf_p}>{ind_num(prev_total_cv) if prev_total_cv else '—'}</td>" if show_prev else "")
        + f"<td {tf}>{ind_num(total_cv)}</td>"
        + (f"<td {tf}>{_chg_cell(total_cv, prev_total_cv)}</td>" if show_prev else "")
        + f"<td {tf}>{ind_num(gain)}</td>"
        f"<td {tf}>{tot_ret_s}</td>"
        f"<td {tf}>100.00%</td>"
        f"</tr>"
    )

    desktop = (
        f"<div class='wt-desk' style='overflow-x:auto'>"
        f"<table style='width:100%;border-collapse:collapse;font-size:.85em'>"
        f"<thead><tr>"
        f"<th {th_l}>Asset class</th>"
        f"<th {th}>Invested</th>"
        + (f"<th {th_p}>Prev day close</th>" if show_prev else "")
        + f"<th {th}>Current value</th>"
        + (f"<th {th}>Change</th>" if show_prev else "")
        + f"<th {th}>Total Gain/Loss</th>"
        f"<th {th}>Return %</th>"
        f"<th {th}>Alloc %</th>"
        f"</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        f"</table></div>"
    )

    # ── MOBILE CARDS ────────────────────────────────────────────────────────
    cards = ""
    for name, inv, cv, gl, ret, alloc, has_gl, prev_cv in computed:
        chg_html = ""
        if show_prev and prev_cv:
            chg   = cv - prev_cv
            cpct  = abs(chg / prev_cv * 100) if prev_cv else 0
            color = "green" if chg >= 0 else "red"
            chg_html = (f'<div style="font-size:.82em;color:{color};margin-top:2px">'
                        f'{ind_num(abs(chg), decimals=0)} ({cpct:.2f}%)</div>')
        prev_html = (f'<div style="font-size:.78em;color:#6b4fa0;margin-top:1px">'
                     f'prev: {ind_num(prev_cv)}</div>') if (show_prev and prev_cv) else ""
        ret_alloc = (f'<div style="font-size:.78em;color:#888;margin-top:2px">'
                     + (f'{ret:.2f}% return · ' if has_gl and ret is not None else "")
                     + f'{alloc:.2f}% alloc</div>')
        cards += (
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start;'
            f'padding:10px 14px;border-bottom:.5px solid #eee">'
            f'<div style="font-size:.95em;font-weight:500;padding-top:2px">{name}</div>'
            f'<div style="text-align:right">'
            f'<div style="font-size:1.05em;font-weight:600">{ind_num(cv)}</div>'
            f'{prev_html}{chg_html}{ret_alloc}'
            f'</div></div>'
        )

    # Total card
    tot_chg_html = ""
    if show_prev and prev_total_cv:
        chg   = total_cv - prev_total_cv
        cpct  = abs(chg / prev_total_cv * 100) if prev_total_cv else 0
        color = "green" if chg >= 0 else "red"
        tot_chg_html = (f'<div style="font-size:.75em;color:{color};margin-top:2px">'
                        f'{ind_num(abs(chg), decimals=0)} ({cpct:.2f}%)</div>')
    tot_prev_html = (f'<div style="font-size:.7em;color:#6b4fa0;margin-top:1px">'
                     f'prev: {ind_num(prev_total_cv)}</div>') if (show_prev and prev_total_cv) else ""
    tot_ret_meta  = (f'<div style="font-size:.7em;color:#888;margin-top:2px">'
                     + (f'{tot_ret:.2f}% return' if tot_ret is not None else "") + '</div>')
    cards += (
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;'
        f'padding:10px 14px;background:#f0f2f6;border-top:1px solid #ccc">'
        f'<div style="font-size:.9em;font-weight:600;padding-top:2px">Total</div>'
        f'<div style="text-align:right">'
        f'<div style="font-size:1em;font-weight:700">{ind_num(total_cv)}</div>'
        f'{tot_prev_html}{tot_chg_html}{tot_ret_meta}'
        f'</div></div>'
    )

    mobile = (
        f'<div class="wt-mob" style="border:.5px solid #ddd;border-radius:8px;overflow:hidden">'
        f'{cards}</div>'
    )

    return desktop + mobile


st.markdown(_build_table(), unsafe_allow_html=True)
st.caption("Insurance = Surrender Value  |  Bank/FD/UAE shown as INR equivalent  |  "
           "Prev day close = latest snapshot before today's market open")

st.divider()

# ── Last Data Refresh status ──────────────────────────────────────────────────
with st.expander("🔄 Last Data Refresh", expanded=False):
    import datetime as _dt

    _IST   = _dt.timezone(_dt.timedelta(hours=5, minutes=30))
    _today = _dt.datetime.now(_IST).date()

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
