"""Backup — download a full JSON snapshot of all Supabase config & history tables."""
import sys, os, json, datetime, urllib.request, urllib.error
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from utils.sidebar import render_sidebar
from utils.db import fetch

_GH_OWNER    = "veenayys-rgb"
_GH_REPO     = "Wealth-Tracker"
_GH_WORKFLOW = "weekly_backup.yml"


def _trigger_backup_workflow() -> tuple[bool, str]:
    """Trigger the weekly_backup workflow via GitHub API. Returns (success, message)."""
    try:
        pat = st.secrets["github"]["pat"]
    except KeyError:
        return False, "GitHub PAT not configured — add `[github] pat = ...` to Streamlit secrets."
    url     = f"https://api.github.com/repos/{_GH_OWNER}/{_GH_REPO}/actions/workflows/{_GH_WORKFLOW}/dispatches"
    payload = json.dumps({"ref": "main"}).encode()
    req     = urllib.request.Request(
        url, data=payload, method="POST",
        headers={
            "Authorization": f"Bearer {pat}",
            "Accept":        "application/vnd.github.v3+json",
            "Content-Type":  "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 204:
                return True, "✅ Backup workflow triggered — check GitHub Actions in ~1 min."
            return False, f"Unexpected response: {resp.status}"
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return False, f"GitHub API error {e.code}: {body}"
    except Exception as e:
        return False, str(e)

st.set_page_config(page_title="Backup | Wealth Tracker", page_icon="💾", layout="wide")
st.title("💾 Backup")
render_sidebar()

st.markdown(
    "Download a full snapshot of all your data. The JSON file can be used to restore "
    "your Supabase tables if anything is ever lost. Store it somewhere safe — Google Drive, "
    "iCloud, email to yourself, etc."
)

_CONFIG_TABLES = [
    "cfg_equity_india",
    "cfg_equity_international",
    "cfg_mutual_funds",
    "cfg_bank_india",
    "cfg_bank_uae",
    "cfg_fixed_deposits",
    "cfg_insurance",
    "cfg_watchlist",
    "cfg_nominees",
    "cfg_demat_accounts",
]

_HISTORY_TABLES = [
    "portfolio_history",
    "portfolio_history_mom",
    "dashboard_snapshots",
]

ALL_TABLES = _CONFIG_TABLES + _HISTORY_TABLES


@st.cache_data(ttl=60)
def _load_all() -> dict:
    out = {}
    for t in ALL_TABLES:
        try:
            out[t] = fetch(t)
        except Exception as e:
            out[t] = []
            st.warning(f"Could not load {t}: {e}")
    return out


with st.spinner("Loading tables…"):
    data = _load_all()

# ── Summary table ─────────────────────────────────────────────────────────────
st.subheader("Table Summary")
summary_rows = []
for t in ALL_TABLES:
    rows = data.get(t, [])
    summary_rows.append({
        "Table":     t,
        "Category":  "Config" if t in _CONFIG_TABLES else "History",
        "Row Count": len(rows),
    })

import pandas as pd
st.dataframe(pd.DataFrame(summary_rows), hide_index=True, use_container_width=True)

total_rows = sum(r["Row Count"] for r in summary_rows)
st.caption(f"Total rows across all tables: **{total_rows}**")

# ── Download ──────────────────────────────────────────────────────────────────
st.divider()

# ── Trigger GitHub Actions backup ─────────────────────────────────────────────
st.subheader("Run Automated Backup Now")
st.caption("Triggers the GitHub Actions workflow — backs up to the repo's `backups/` folder without needing to open GitHub.")
if st.button("🚀 Trigger GitHub Backup", type="secondary"):
    ok, msg = _trigger_backup_workflow()
    if ok:
        st.success(msg)
    else:
        st.error(msg)

st.divider()
st.subheader("Download")

payload = {
    "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
    "tables":      data,
}
json_bytes = json.dumps(payload, indent=2, default=str).encode("utf-8")
date_str   = datetime.date.today().isoformat()

col1, col2 = st.columns([1, 3])
col1.download_button(
    label="⬇️ Download Full Backup (JSON)",
    data=json_bytes,
    file_name=f"wealthtracker_backup_{date_str}.json",
    mime="application/json",
    type="primary",
    use_container_width=True,
)
col2.info(
    f"File: `wealthtracker_backup_{date_str}.json`  |  "
    f"Size: ~{len(json_bytes)/1024:.0f} KB  |  "
    f"Tables: {len(ALL_TABLES)}  |  "
    f"Rows: {total_rows}"
)

st.divider()
st.caption(
    "💡 **Automatic weekly backup** also runs every Sunday via GitHub Actions — "
    "check the `backups/` folder in your GitHub repo for the last 8 weeks of snapshots."
)
