"""Supabase client — used by all fetchers."""
import os, pathlib
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://bopqwksvunejedhgdvxv.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# Fall back to .streamlit/secrets.toml when running outside watcher/GitHub Actions
if not SUPABASE_KEY:
    _secrets = pathlib.Path(__file__).parents[1] / ".streamlit" / "secrets.toml"
    if _secrets.exists():
        import re
        _m = re.search(r'service_key\s*=\s*"([^"]+)"', _secrets.read_text())
        if _m:
            SUPABASE_KEY = _m.group(1)

_client: Client | None = None

def get_client() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_SERVICE_KEY env var not set")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def upsert(table: str, rows: list[dict], conflict_col: str = "symbol"):
    """Upsert rows into a Supabase table."""
    if not rows:
        return
    get_client().table(table).upsert(rows, on_conflict=conflict_col).execute()


def fetch_cfg(table: str, owner: str = None) -> list[dict]:
    """Read holdings from a cfg_* table. Optionally filter by owner."""
    q = get_client().table(table).select("*")
    if owner:
        q = q.eq("owner", owner)
    rows = q.execute().data
    return [{k: v for k, v in r.items() if k != "id"} for r in rows]
