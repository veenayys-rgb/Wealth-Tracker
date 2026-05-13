"""Supabase read-only client for Streamlit app."""
import streamlit as st
from supabase import create_client, Client

@st.cache_resource
def get_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["anon_key"]
    return create_client(url, key)


def fetch(table: str, columns: str = "*") -> list[dict]:
    return get_client().table(table).select(columns).execute().data


def fetch_one(table: str, col: str, val: str) -> dict | None:
    rows = get_client().table(table).select("*").eq(col, val).execute().data
    return rows[0] if rows else None


def get_forex() -> dict:
    """Returns {AED_INR: float, USD_INR: float}"""
    rows = fetch("forex_rates", "pair,rate")
    return {r["pair"]: float(r["rate"]) for r in rows}
