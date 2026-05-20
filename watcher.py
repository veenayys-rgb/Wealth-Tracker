"""
Wealth Tracker Watcher
Run once in Terminal at the start of the day:
  python3 ~/Library/Mobile\ Documents/com~apple~CloudDocs/WealthTracker/watcher.py

Two ways to trigger the fetcher:
  1. Auto-trigger at 4:05 PM IST on weekdays (Mon-Fri)
  2. Manual trigger — drop a file at ~/Documents/run_trigger.txt
"""
import os, time, subprocess, datetime

ICLOUD       = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/WealthTracker")
TRIGGER_FILE = os.path.expanduser("~/Documents/run_trigger.txt")
FETCHER      = os.path.join(ICLOUD, "fetcher", "run.py")
PYTHON       = "/usr/local/bin/python3"

IST       = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
AUTO_HOUR = 16
AUTO_MIN  =  5   # 4:05 PM IST — 5 min buffer after NSE close


def stamp():
    return datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S")


def run_fetcher(reason: str):
    print(f"\n🔔  {reason} — {stamp()}")
    print("▶️   Running fetcher/run.py...")
    print("─" * 60)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(ICLOUD, "fetcher")
    subprocess.run([PYTHON, FETCHER], env=env)
    print("─" * 60)
    print(f"✅  Done — watching again...\n")


print("─" * 60)
print("💰  WEALTH TRACKER WATCHER")
print(f"    {stamp()}")
print("─" * 60)
print(f"📂  Fetcher  : {FETCHER}")
print(f"👀  Manual   : drop {TRIGGER_FILE}")
print(f"⏰  Auto-run : {AUTO_HOUR:02d}:{AUTO_MIN:02d} IST on weekdays (Mon-Fri)")
print(f"    Press Ctrl+C to stop\n")

if not os.path.exists(FETCHER):
    print(f"❌  fetcher/run.py not found at {FETCHER}")
    exit(1)

last_auto_date = None   # prevents double-firing on the same day

while True:
    now_ist = datetime.datetime.now(IST)
    today   = now_ist.date()

    # Manual trigger via file
    if os.path.exists(TRIGGER_FILE):
        try:
            os.remove(TRIGGER_FILE)
        except Exception:
            pass
        run_fetcher("Manual trigger detected")

    # Auto-trigger at 4:05 PM IST on weekdays
    elif (last_auto_date != today
          and now_ist.weekday() < 5          # Mon-Fri only
          and now_ist.hour == AUTO_HOUR
          and now_ist.minute >= AUTO_MIN):
        last_auto_date = today
        run_fetcher(f"Auto-trigger — {AUTO_HOUR:02d}:{AUTO_MIN:02d} IST")

    time.sleep(15)   # check every 15 seconds
