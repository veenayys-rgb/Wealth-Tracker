"""Backup all Supabase config & history tables to a dated JSON file."""
import json, os, datetime
from db import get_client

TABLES = [
    "cfg_equity_india",
    "cfg_equity_international",
    "cfg_mutual_funds",
    "cfg_bank_india",
    "cfg_bank_uae",
    "cfg_fixed_deposits",
    "cfg_insurance",
    "cfg_watchlist",
    "cfg_nominees",
    "cfg_demat_accounts",
    "portfolio_history",
    "portfolio_history_mom",
    "dashboard_snapshots",
]


def run(out_dir: str = "backups") -> str:
    os.makedirs(out_dir, exist_ok=True)
    db = get_client()

    payload = {
        "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
        "tables":      {},
    }

    total = 0
    for table in TABLES:
        try:
            rows = db.table(table).select("*").execute().data
            payload["tables"][table] = rows
            total += len(rows)
            print(f"  ✅  {table}: {len(rows)} rows")
        except Exception as e:
            payload["tables"][table] = []
            print(f"  ❌  {table}: {e}")

    date_str = datetime.date.today().isoformat()
    out_file = os.path.join(out_dir, f"{date_str}.json")
    with open(out_file, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    print(f"\n📦  {total} rows → {out_file}")
    return out_file


if __name__ == "__main__":
    import sys
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "backups"
    run(out_dir)
