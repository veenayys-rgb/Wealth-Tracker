"""
One-time script: import Portfolio History from Excel into Supabase.
Run from the fetcher/ directory:
    cd fetcher && python import_history.py
Requires SUPABASE_SERVICE_KEY env var to be set.
"""
import os, sys
import pandas as pd
from db import upsert

EXCEL = os.path.expanduser("~/Desktop/Portfolio History.xlsx")


def main():
    if not os.path.exists(EXCEL):
        print(f"❌  File not found: {EXCEL}")
        sys.exit(1)

    df = pd.read_excel(EXCEL, sheet_name="Portfolio History")
    df.columns = df.columns.str.strip()
    print(f"✅  Loaded {len(df)} rows from Excel")

    rows = []
    for _, r in df.iterrows():
        date = r["Date"]
        if pd.isna(date):
            continue
        # Parse date
        if hasattr(date, "date"):
            date_str = date.date().isoformat()
        else:
            date_str = str(date)[:10]

        total_inv = float(r.get("Total Invested", 0) or 0)
        total_cv  = float(r.get("Total CV", 0) or 0)
        gain      = float(r.get("Gain/Loss", 0) or 0)
        ret_pct   = round((gain / total_inv * 100), 4) if total_inv > 0 else 0.0

        # Excel has no Anusha columns — default to 0
        rows.append({
            "date":           date_str,
            "shares_invested": float(r.get("Shares Invested", 0) or 0),
            "shares_cv":       float(r.get("Shares CV", 0) or 0),
            "mf_inv_vinay":    float(r.get("MF Invested - Vinay", 0) or 0),
            "mf_cv_vinay":     float(r.get("MF CV - Vinay", 0) or 0),
            "mf_inv_harsh":    float(r.get("MF Invested - Harsh", 0) or 0),
            "mf_cv_harsh":     float(r.get("MF CV - Harsh", 0) or 0),
            "mf_inv_anusha":   0.0,
            "mf_cv_anusha":    0.0,
            "total_invested":  round(total_inv, 2),
            "total_cv":        round(total_cv, 2),
            "gain_loss":       round(gain, 2),
            "return_pct":      ret_pct,
        })

    upsert("portfolio_history", rows, conflict_col="date")
    print(f"✅  {len(rows)} rows upserted to portfolio_history")
    for r in rows[:3]:
        print(f"   {r['date']}  Invested: ₹{r['total_invested']:>14,.2f}  CV: ₹{r['total_cv']:>14,.2f}")
    print("   ...")


if __name__ == "__main__":
    main()
