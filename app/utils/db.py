"""Supabase clients for Streamlit app."""  # noqa
import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["anon_key"]
    return create_client(url, key)


@st.cache_resource
def _service_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["service_key"]
    return create_client(url, key)


def fetch(table: str, columns: str = "*") -> list[dict]:
    return get_client().table(table).select(columns).execute().data


def fetch_latest_ts(table: str, ts_col: str = "fetched_at") -> str | None:
    """Return the single most recent value of ts_col from table, or None."""
    rows = (get_client().table(table).select(ts_col)
            .order(ts_col, desc=True).limit(1).execute().data)
    return rows[0][ts_col] if rows else None


def fetch_one(table: str, col: str, val: str) -> dict | None:
    rows = get_client().table(table).select("*").eq(col, val).execute().data
    return rows[0] if rows else None


def get_forex() -> dict:
    """Returns {AED_INR, USD_INR, NIFTY50, SENSEX, ...} as floats."""
    rows = fetch("forex_rates", "pair,rate")
    return {r["pair"]: float(r["rate"]) for r in rows}


def service_upsert(table: str, rows: list[dict], conflict_col: str = "symbol"):
    """Upsert using service key — for refreshing price tables from the app."""
    if rows:
        _service_client().table(table).upsert(rows, on_conflict=conflict_col).execute()


def service_delete(table: str, col: str, values: list):
    """Delete rows where col is in values, using service key."""
    if values:
        _service_client().table(table).delete().in_(col, values).execute()
