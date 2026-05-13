"""Load static config files from iCloud Drive."""
import json, os

ICLOUD = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/WealthTracker")
CONFIG = os.path.join(ICLOUD, "config")


def load(filename: str) -> list:
    path = os.path.join(CONFIG, filename)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def save(filename: str, data: list):
    path = os.path.join(CONFIG, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
