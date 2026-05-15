"""Config: load/save holdings data from Supabase."""
import streamlit as st
from supabase import create_client, Client

# Maps filename → (supabase_table, owner_filter_or_None)
TABLE_MAP = {
    # equity — all owners combined (used by dashboard/fetcher)
    "equity_india.json":               ("cfg_equity_india",         None),
    "equity_international.json":       ("cfg_equity_international", None),
    # equity — per owner (used by UI pages)
    "equity_india_vinay.json":         ("cfg_equity_india",         "Vinay"),
    "equity_india_harsh.json":         ("cfg_equity_india",         "Harsh"),
    "equity_india_anusha.json":        ("cfg_equity_india",         "Anusha"),
    "equity_intl_vinay.json":          ("cfg_equity_international", "Vinay"),
    "equity_intl_harsh.json":          ("cfg_equity_international", "Harsh"),
    "equity_intl_anusha.json":         ("cfg_equity_international", "Anusha"),
    # mutual funds
    "mutual_funds_vinay.json":         ("cfg_mutual_funds",         "Vinay"),
    "mutual_funds_harsh.json":         ("cfg_mutual_funds",         "Harsh"),
    "mutual_funds_anusha.json":        ("cfg_mutual_funds",         "Anusha"),
    "watchlist.json":                  ("cfg_watchlist",            None),
    "bank_india.json":                 ("cfg_bank_india",           None),
    "bank_uae.json":                   ("cfg_bank_uae",             None),
    "fixed_deposits.json":             ("cfg_fixed_deposits",       None),
    "insurance.json":                  ("cfg_insurance",            None),
}


@st.cache_resource
def _client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["anon_key"]
    return create_client(url, key)


@st.cache_resource
def _write_client() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["service_key"]
    return create_client(url, key)


def load(filename: str) -> list:
    table, owner = TABLE_MAP[filename]
    q = _client().table(table).select("*")
    if owner:
        q = q.eq("owner", owner)
    rows = q.order("id").execute().data
    return [{k: v for k, v in r.items() if k != "id"} for r in rows]


def save(filename: str, data: list):
    table, owner = TABLE_MAP[filename]
    client = _write_client()
    dq = client.table(table).delete()
    if owner:
        dq = dq.eq("owner", owner)
    else:
        dq = dq.gte("id", 0)
    dq.execute()
    if data:
        rows = [{**d, "owner": owner} for d in data] if owner else list(data)
        client.table(table).insert(rows).execute()
