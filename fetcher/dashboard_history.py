"""
Dashboard History recorder.
Runs after prices are fetched. Inserts a full per-owner per-category snapshot
into dashboard_snapshots only when the NSE market is closed.
"""
import datetime
from db import get_client, fetch_cfg

IST      = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
OPEN_HR  = 9
CLOSE_HR = 15
CLOSE_MN = 30

_OWNERS = ["Vinay", "Harsh", "Anusha", "Mom"]
_CATS   = ["india_eq", "mf", "intl_eq", "bank_india", "bank_uae", "fd", "insurance"]


def market_is_closed() -> bool:
    now = datetime.datetime.now(IST)
    if now.weekday() >= 5:
        return True
    open_time  = now.replace(hour=OPEN_HR,  minute=0,       second=0, microsecond=0)
    close_time = now.replace(hour=CLOSE_HR, minute=CLOSE_MN, second=0, microsecond=0)
    return now < open_time or now >= close_time


def _fetch(table: str) -> list[dict]:
    return get_client().table(table).select("*").execute().data


def _fx(forex: dict, currency: str) -> float:
    if currency == "AED": return forex.get("AED_INR", 0.0)
    if currency == "USD": return forex.get("USD_INR", 0.0)
    return 1.0


def _compute_snapshot() -> dict:
    db = get_client()

    # Forex rates
    forex = {r["pair"]: float(r["rate"]) for r in db.table("forex_rates").select("pair,rate").execute().data}

    # Prices / NAVs
    eq_prices   = {r["symbol"]: float(r["price"]) for r in _fetch("equity_india_prices")         if r.get("price")}
    mf_navs     = {r["isin"]:   float(r["nav"])   for r in _fetch("mf_navs")                     if r.get("nav")}
    intl_prices = {r["symbol"]: float(r["price"]) for r in _fetch("equity_international_prices") if r.get("price")}

    # Holdings
    all_india_eq = fetch_cfg("cfg_equity_india")
    all_intl_eq  = fetch_cfg("cfg_equity_international")
    all_mf       = fetch_cfg("cfg_mutual_funds")
    all_bank_in  = _fetch("cfg_bank_india")
    all_bank_uae = _fetch("cfg_bank_uae")
    all_fd       = _fetch("cfg_fixed_deposits")
    all_ins      = _fetch("cfg_insurance")

    snap = {}
    for owner in _OWNERS:
        p = owner.lower()

        # India Equity
        ie = 0.0
        for h in all_india_eq:
            if h.get("owner") != owner:
                continue
            price = eq_prices.get(h.get("symbol", "").upper(), 0)
            qty   = float(h.get("qty", 0))
            ie   += qty * price if price else qty * float(h.get("avg_cost", 0))
        snap[f"{p}_india_eq"] = round(ie, 2)

        # Mutual Funds
        mf = 0.0
        for h in all_mf:
            if h.get("owner") != owner:
                continue
            nav   = mf_navs.get(h.get("isin", "").upper(), 0)
            units = float(h.get("units", 0))
            mf   += units * nav if nav else units * float(h.get("avg_nav", 0))
        snap[f"{p}_mf"] = round(mf, 2)

        # International Equity (Mom has no intl holdings)
        intl = 0.0
        if owner != "Mom":
            for h in all_intl_eq:
                if h.get("owner") != owner:
                    continue
                price = intl_prices.get(h.get("symbol", "").upper(), 0)
                curr  = h.get("currency", "AED")
                qty   = float(h.get("qty", 0))
                cost  = float(h.get("avg_cost", 0))
                intl += qty * price * _fx(forex, curr) if price else qty * cost * _fx(forex, curr)
        snap[f"{p}_intl_eq"] = round(intl, 2)

        # Bank India
        bank_in = sum(
            float(b.get("balance", 0)) for b in all_bank_in
            if b.get("owner", "Vinay") == owner
        )
        snap[f"{p}_bank_india"] = round(bank_in, 2)

        # Bank UAE (Mom has no UAE account)
        bank_uae = 0.0
        if owner != "Mom":
            for b in all_bank_uae:
                if b.get("owner", "Vinay") != owner:
                    continue
                bank_uae += float(b.get("balance_aed", 0)) * _fx(forex, b.get("currency", "AED"))
        snap[f"{p}_bank_uae"] = round(bank_uae, 2)

        # Fixed Deposits
        fd = sum(
            float(r.get("amount", 0)) * _fx(forex, r.get("currency", "INR"))
            for r in all_fd if r.get("owner", "Vinay") == owner
        )
        snap[f"{p}_fd"] = round(fd, 2)

        # Insurance (Mom has no insurance)
        ins = 0.0
        if owner != "Mom":
            for r in all_ins:
                if r.get("owner", "Vinay") != owner:
                    continue
                ins += float(r.get("surrender_value", 0)) * _fx(forex, r.get("currency", "INR"))
        snap[f"{p}_insurance"] = round(ins, 2)

    return snap


def record_dashboard_snapshot():
    if not market_is_closed():
        now = datetime.datetime.now(IST).strftime("%H:%M IST")
        print(f"\n⏳  Market open ({now}) — dashboard snapshot skipped.")
        return

    print(f"\n📸  Recording dashboard snapshot…")
    snap = _compute_snapshot()
    get_client().table("dashboard_snapshots").insert(snap).execute()

    family_total = sum(snap.get(f"{o.lower()}_{c}", 0) for o in ["Vinay", "Harsh", "Anusha"] for c in _CATS)
    print(f"   ✅  Dashboard snapshot saved")
    print(f"   Family Total CV: ₹{family_total:>14,.2f}")
