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
    return _service_client().table(table).select(columns).execute().data


def fetch_latest_ts(table: str, ts_col: str = "fetched_at") -> str | None:
    """Return the single most recent value of ts_col from table, or None."""
    rows = (_service_client().table(table).select(ts_col)
            .order(ts_col, desc=True).limit(1).execute().data)
    return rows[0][ts_col] if rows else None


def fetch_one(table: str, col: str, val: str) -> dict | None:
    rows = _service_client().table(table).select("*").eq(col, val).execute().data
    return rows[0] if rows else None


def get_forex() -> dict:
    """Returns {AED_INR, USD_INR, NIFTY50, SENSEX, ...} as floats."""
    rows = fetch("forex_rates", "pair,rate")
    return {r["pair"]: float(r["rate"]) for r in rows}


def service_upsert(table: str, rows: list[dict], conflict_col: str = "symbol"):
    """Upsert using service key — for refreshing price tables from the app."""
    if rows:
        _service_client().table(table).upsert(rows, on_conflict=conflict_col).execute()


def service_insert(table: str, row: dict) -> dict:
    """Insert a single row using service key; returns the inserted row."""
    result = _service_client().table(table).insert(row).execute()
    return result.data[0] if result.data else {}


def service_delete(table: str, col: str, values: list):
    """Delete rows where col is in values, using service key."""
    if values:
        _service_client().table(table).delete().in_(col, values).execute()


def service_delete_match(table: str, match: dict):
    """Delete rows matching ALL key=value pairs, using service key."""
    q = _service_client().table(table).delete()
    for col, val in match.items():
        q = q.eq(col, val)
    q.execute()


def service_update(table: str, match: dict, updates: dict):
    """Update rows matching ALL key=value pairs, using service key."""
    q = _service_client().table(table).update(updates)
    for col, val in match.items():
        q = q.eq(col, val)
    q.execute()


def upload_policy_doc(owner: str, policy_no: str, filename: str,
                      data: bytes, mime: str) -> str:
    """Upload a file to the policy-docs bucket; returns its public URL."""
    path = f"{owner}/{policy_no or 'misc'}/{filename}"
    _service_client().storage.from_("policy-docs").upload(
        path, data, {"content-type": mime, "upsert": "true"}
    )
    return _service_client().storage.from_("policy-docs").get_public_url(path)


def delete_policy_doc(url: str):
    """Remove a file from the policy-docs bucket given its public URL."""
    try:
        path = url.split("/storage/v1/object/public/policy-docs/")[1]
        _service_client().storage.from_("policy-docs").remove([path])
    except Exception:
        pass


def fetch_nominees_map(asset_type: str, owner: str | None = None) -> dict:
    """Returns {asset_ref: [list_of_rows]} for nominees of the given asset_type."""
    q = _service_client().table("cfg_nominees").select("*").eq("asset_type", asset_type)
    if owner:
        q = q.eq("owner", owner)
    result: dict[str, list] = {}
    for r in q.execute().data:
        result.setdefault(r["asset_ref"], []).append(r)
    return result


def save_nominees(asset_type: str, asset_ref: str, owner: str, label: str,
                  nominees: list[dict]):
    """Replace all nominees for asset_type + asset_ref.
    Each dict: nominee_name, share_pct, relationship, nomination_registered, notes."""
    service_delete_match("cfg_nominees", {"asset_type": asset_type, "asset_ref": asset_ref})
    for n in nominees:
        name = str(n.get("nominee_name", "")).strip()
        if name:
            service_insert("cfg_nominees", {
                "asset_type":            asset_type,
                "asset_ref":             asset_ref,
                "owner":                 owner,
                "label":                 label,
                "nominee_name":          name,
                "share_pct":             float(n.get("share_pct", 0)),
                "relationship":          str(n.get("relationship", "") or ""),
                "nomination_registered": bool(n.get("nomination_registered", False)),
                "notes":                 str(n.get("notes", "") or ""),
            })


def fetch_demat_accounts(owner: str | None = None) -> list[dict]:
    """Fetch demat accounts from cfg_demat_accounts, optionally filtered by owner."""
    q = _service_client().table("cfg_demat_accounts").select("*")
    if owner:
        q = q.eq("owner", owner)
    return q.order("id").execute().data
