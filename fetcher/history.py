"""
Portfolio History recorder.
Runs after prices are fetched. Records a daily snapshot only when
the NSE market is closed (weekends, holidays, or after 3:30 PM IST).
"""
import datetime
from db import get_client, upsert, fetch_cfg

IST      = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
CLOSE_HR = 15
CLOSE_MN = 30


def market_is_closed() -> bool:
    """True if NSE market is currently closed."""
    now = datetime.datetime.now(IST)
    if now.weekday() >= 5:          # Saturday / Sunday
        return True
    close_time = now.replace(hour=CLOSE_HR, minute=CLOSE_MN, second=0, microsecond=0)
    return now >= close_time


def get_latest_prices() -> dict:
    """Fetch latest prices from Supabase."""
    db = get_client()
    eq = {r["symbol"]: r["price"] for r in
          db.table("equity_india_prices").select("symbol,price").execute().data}
    navs = {r["isin"]: r["nav"] for r in
            db.table("mf_navs").select("isin,nav").execute().data}
    return eq, navs


_FAMILY = {"Vinay", "Harsh", "Anusha"}   # owners included in family portfolio history


def compute_snapshot(eq_prices: dict, mf_navs: dict) -> dict:
    eq_invested = eq_cv = 0.0

    for h in fetch_cfg("cfg_equity_india"):
        # Exclude non-family owners (e.g. Mom) from the family snapshot
        if h.get("owner") and h["owner"] not in _FAMILY:
            continue
        sym     = h["symbol"].upper()
        price   = eq_prices.get(sym, 0)
        qty     = float(h.get("qty", 0))
        cost    = float(h.get("avg_cost", 0))
        inv     = qty * cost
        eq_invested += inv
        eq_cv       += qty * price if price > 0 else inv

    mf_data = {}
    for owner in ["Vinay", "Harsh", "Anusha"]:
        inv = cv = 0.0
        for h in fetch_cfg("cfg_mutual_funds", owner=owner):
            isin  = h.get("isin", "").upper()
            units = float(h.get("units", 0))
            anav  = float(h.get("avg_nav", 0))
            nav   = mf_navs.get(isin, 0)
            inv  += units * anav
            cv   += units * nav if nav > 0 else units * anav
        mf_data[owner.lower()] = {"invested": round(inv, 2), "cv": round(cv, 2)}

    total_inv = eq_invested + sum(v["invested"] for v in mf_data.values())
    total_cv  = eq_cv       + sum(v["cv"]       for v in mf_data.values())
    gain      = total_cv - total_inv
    ret_pct   = round((gain / total_inv * 100), 4) if total_inv > 0 else 0

    return {
        "date":           datetime.date.today().isoformat(),
        "shares_invested": round(eq_invested, 2),
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


def compute_mom_snapshot(eq_prices: dict, mf_navs: dict) -> dict:
    eq_invested = eq_cv = 0.0
    for h in fetch_cfg("cfg_equity_india", owner="Mom"):
        sym   = h.get("symbol", "").upper()
        price = eq_prices.get(sym, 0)
        qty   = float(h.get("qty", 0))
        cost  = float(h.get("avg_cost", 0))
        inv   = qty * cost
        eq_invested += inv
        eq_cv       += qty * price if price > 0 else inv

    mf_invested = mf_cv = 0.0
    for h in fetch_cfg("cfg_mutual_funds", owner="Mom"):
        isin  = h.get("isin", "").upper()
        units = float(h.get("units", 0))
        anav  = float(h.get("avg_nav", 0))
        nav   = mf_navs.get(isin, 0)
        inv   = units * anav
        mf_invested += inv
        mf_cv       += units * nav if nav > 0 else inv

    total_inv = eq_invested + mf_invested
    total_cv  = eq_cv + mf_cv
    gain      = total_cv - total_inv
    ret_pct   = round((gain / total_inv * 100), 4) if total_inv > 0 else 0

    return {
        "date":          datetime.date.today().isoformat(),
        "eq_invested":   round(eq_invested, 2),
        "eq_cv":         round(eq_cv, 2),
        "mf_invested":   round(mf_invested, 2),
        "mf_cv":         round(mf_cv, 2),
        "total_invested": round(total_inv, 2),
        "total_cv":       round(total_cv, 2),
        "gain_loss":      round(gain, 2),
        "return_pct":     ret_pct,
    }


def record_history():
    if not market_is_closed():
        now = datetime.datetime.now(IST).strftime("%H:%M IST")
        print(f"\n⏳  Market open ({now}) — history skipped. Run again after 3:30 PM IST.")
        return

    print(f"\n📅  Market closed — recording portfolio snapshot…")
    eq_prices, mf_navs = get_latest_prices()

    # Family snapshot
    row = compute_snapshot(eq_prices, mf_navs)
    upsert("portfolio_history", [row], conflict_col="date")
    print(f"   ✅  Family snapshot for {row['date']} saved")
    print(f"   Total Invested: ₹{row['total_invested']:>14,.2f}")
    print(f"   Total CV:       ₹{row['total_cv']:>14,.2f}")
    print(f"   Gain/Loss:      ₹{row['gain_loss']:>14,.2f}  ({row['return_pct']:.2f}%)")

    # Mom snapshot
    mom_row = compute_mom_snapshot(eq_prices, mf_navs)
    upsert("portfolio_history_mom", [mom_row], conflict_col="date")
    print(f"   ✅  Mom snapshot for {mom_row['date']} saved")
    print(f"   Total Invested: ₹{mom_row['total_invested']:>14,.2f}")
    print(f"   Total CV:       ₹{mom_row['total_cv']:>14,.2f}")
