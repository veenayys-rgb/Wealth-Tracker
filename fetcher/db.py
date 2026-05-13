"""Supabase client — used by all fetchers."""
import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://bopqwksvunejedhgdvxv.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")   # service key — set in env

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
