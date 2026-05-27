# Wealth Tracker — Developer Conventions

This file is read by Claude Code before making any changes.
Follow every rule below without exception.

---

## 1. Streamlit Cloud — Module Cache Busting

**Problem:** Streamlit Cloud warm-reloads page files without restarting Python.
Old utility modules stay cached in `sys.modules`, so new exports cause `ImportError`.

**Rule:** Whenever you add a new function or export to ANY file in `app/utils/`
(`db.py`, `fmt.py`, `sidebar.py`, `config.py`), you MUST bump `__version__`
in `app/utils/__init__.py` **in the same commit**.

```python
# app/utils/__init__.py
__version__ = "1.3"   # was 1.2 → bumped because fetch_xyz added to db.py
```

Never use `# noqa` comment hacks as a fix after the fact — bump the version proactively.

---

## 2. Date & Time Display

**Rule:** ALL timestamps and dates shown to the user must use these helpers from `utils/fmt.py`.
Never format dates or times manually inline.

| Use case | Function | Output format |
|---|---|---|
| Display a stored date (ISO or date obj) | `fmt_date(d)` | `27-May-2026` |
| Display a UTC timestamp from DB | `utc_to_ist(ts)` | `27-May-2026 16:08 IST` |
| Parse a user-entered / stored date | `parse_date(d)` | `datetime.date` object |

**Examples:**
```python
# ✅ Correct
st.caption(f"Last fetched: {utc_to_ist(max(r['fetched_at'] for r in rows))}")
fmt_date(h.get("buy_date", ""))

# ❌ Wrong
last_fetch = prices_rows[0]["fetched_at"][:19].replace("T", " ")
st.caption(f"Last fetched: {last_fetch} UTC")
```

---

## 3. fetched_at Display — Always Use max()

**Problem:** `rows[0]["fetched_at"]` picks an arbitrary row (first by DB insertion order).
Some rows may have older timestamps if their individual fetch failed.

**Rule:** Always take the max across all rows:
```python
# ✅ Correct
last_fetch = utc_to_ist(max((r["fetched_at"] for r in rows), default=None)) if rows else "—"

# ❌ Wrong
last_fetch = rows[0]["fetched_at"][:19].replace("T", " ")
```

---

## 4. Number Formatting

**Rule:** ALL monetary values shown to the user must use `ind_num()` from `utils/fmt.py`.
This formats numbers in the Indian system (₹ 1,00,000.00).

```python
from utils.fmt import ind_num, plain_num

ind_num(value)           # ₹ 1,00,000.00  — for INR values
plain_num(value)         # 1,00,000.00    — for non-INR / foreign currency
ind_num(value, decimals=0)  # ₹ 1,00,000   — for axis labels / rounded display
```

Never use Python's built-in `f"{value:,.2f}"` for user-facing monetary display.

---

## 5. Plotly Chart Y-Axis — Indian Number Format

**Rule:** All Plotly chart y-axes must use `indian_axis_ticks()` instead of `tickformat`.

```python
from utils.fmt import indian_axis_ticks

tickvals, ticktext = indian_axis_ticks(y_min, y_max)
fig.update_layout(
    yaxis=dict(range=[y_min, y_max], tickvals=tickvals, ticktext=ticktext),
)

# ❌ Wrong
fig.update_layout(yaxis=dict(tickformat=",.0f"))
```

---

## 6. Owner / Family Filtering

**Rule:** The "family" portfolio (combined view, portfolio history) includes only
`{"Vinay", "Harsh", "Anusha"}`. Mom has her own separate tables.
Always use this constant — never hardcode individual names.

```python
_FAMILY = {"Vinay", "Harsh", "Anusha"}

# Exclude Mom from family totals:
if h.get("owner") and h["owner"] not in _FAMILY:
    continue
```

Mom's data lives in:
- `portfolio_history_mom` (not `portfolio_history`)
- `cfg_equity_india` with `owner="Mom"`
- `cfg_mutual_funds` with `owner="Mom"`

---

## 7. Database Access Patterns

Use the helpers in `utils/db.py`. Never write raw Supabase queries in page files.

| Function | When to use |
|---|---|
| `fetch(table)` | Read all rows from a table |
| `fetch_one(table, col, val)` | Read a single row by key |
| `fetch_latest_ts(table)` | Get most recent `fetched_at` from a table |
| `service_upsert(table, rows, conflict_col)` | Write / update rows (uses service key) |
| `service_delete(table, col, values)` | Delete rows by key list |
| `get_forex()` | Get `{AED_INR, USD_INR, NIFTY50, SENSEX}` dict |

---

## 8. Mobile Responsive Layout

Mobile CSS is injected globally via `render_sidebar()` in `utils/sidebar.py`.
No per-page CSS needed. The CSS stacks `st.columns` vertically on screens ≤ 768px.

---

## 9. AMFI NAV Date Storage

AMFI returns dates in `DD-MMM-YYYY` format (e.g. `27-May-2026`).
Supabase `nav_date` columns expect ISO format (`YYYY-MM-DD`).

**Rule:** Always convert before upserting:
```python
datetime.datetime.strptime(s.strip(), "%d-%b-%Y").strftime("%Y-%m-%d")
```

This conversion exists in both `app/pages/4_Mutual_Funds.py` and `app/utils/sidebar.py`.
If you add another MF fetch path, apply the same conversion.

---

## 10. Portfolio History Snapshot — When to Record

The snapshot captures end-of-day values. Recording mid-day would capture intra-day noise.

| Trigger | Market-hours gate |
|---|---|
| GitHub Actions (4:05 PM IST auto-run) | Only records if `now >= 3:30 PM IST` |
| Sidebar "Refresh Prices" button | Only records outside 8:00 AM – 3:30 PM IST |
| Weekends | Always records |

The gate is implemented in `_market_closed()` in `utils/sidebar.py`.

---

## 11. Equity Price Fetching — Reliability Order

Always fetch India equity prices in this order of preference:
1. NSE batch via `yf.download([...".NS"], period="5d")` — fastest
2. Individual NSE via `yf.Ticker(sym+".NS").fast_info.last_price` — fallback
3. Individual BSE via `yf.Ticker(sym+".BO").fast_info.last_price` — last resort

Never use `period="2d"` for NSE batch — returns empty outside market hours.
`fast_info.last_price` is the most reliable as it returns the last traded price
regardless of time of day.

---

## 12. Holding Types

India Equity holding types: `["NRE", "NRO", "Resident"]`
Do not add new types without updating all pages that reference this list:
- `app/pages/3_India_Equity.py`
- `app/pages/12_Equity_Recon.py`

---

## 13. Key File Locations

| Purpose | File |
|---|---|
| Shared formatting helpers | `app/utils/fmt.py` |
| Supabase DB helpers | `app/utils/db.py` |
| Sidebar + price refresh logic | `app/utils/sidebar.py` |
| Holdings config (load/save) | `app/utils/config.py` |
| Module cache version | `app/utils/__init__.py` |
| GitHub Actions auto-fetch | `.github/workflows/daily_fetch.yml` |
| Fetcher orchestrator | `fetcher/run.py` |
| Portfolio history recorder | `fetcher/history.py` |
| Supabase table → JSON mapping | `app/utils/config.py` → `TABLE_MAP` |
