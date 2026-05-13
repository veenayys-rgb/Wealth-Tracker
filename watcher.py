"""
Wealth Tracker Watcher
Run once in Terminal at the start of the day:
  python3 ~/Library/Mobile\ Documents/com~apple~CloudDocs/WealthTracker/watcher.py

Watches ~/Documents/ for run_trigger.txt
When found → runs fetcher/run.py → deletes trigger file
"""
import os, time, subprocess, datetime

ICLOUD       = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/WealthTracker")
TRIGGER_FILE = os.path.expanduser("~/Documents/run_trigger.txt")
FETCHER      = os.path.join(ICLOUD, "fetcher", "run.py")
PYTHON       = "/usr/local/bin/python3"

def stamp():
    return datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S")

print("─" * 60)
print("💰  WEALTH TRACKER WATCHER")
print(f"    {stamp()}")
print("─" * 60)
print(f"📂  Fetcher : {FETCHER}")
print(f"👀  Watching: {TRIGGER_FILE}")
print(f"    Press Ctrl+C to stop\n")

if not os.path.exists(FETCHER):
    print(f"❌  fetcher/run.py not found at {FETCHER}")
    exit(1)

while True:
    if os.path.exists(TRIGGER_FILE):
        print(f"\n🔔  Trigger detected — {stamp()}")
        try:
            os.remove(TRIGGER_FILE)
        except Exception:
            pass
        print("▶️   Running fetcher/run.py…")
        print("─" * 60)
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.join(ICLOUD, "fetcher")
        subprocess.run([PYTHON, FETCHER], env=env)
        print("─" * 60)
        print(f"✅  Done — watching again…\n")
    time.sleep(3)
