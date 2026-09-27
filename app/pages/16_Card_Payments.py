"""Card Payments — UAE credit card bills due, synced from the local Card Extractor (table card_dues)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import datetime
from utils.sidebar import render_sidebar
from utils.db      import fetch, service_upsert
from utils.fmt     import fmt_date, parse_date, plain_num, utc_to_ist

st.set_page_config(page_title="Card Payments | Wealth Tracker", page_icon="💳", layout="wide")
st.title("💳 Card Payments")
render_sidebar()

_UAE_TZ = datetime.timezone(datetime.timedelta(hours=4))
today   = datetime.datetime.now(_UAE_TZ).date()

rows = fetch("card_dues")
if not rows:
    st.info("No card statements yet — they appear here after the Card Extractor on the Mac saves them.")
    st.stop()

for r in rows:
    r["due"]  = parse_date(r.get("due_date"))
    r["paid"] = bool(r.get("paid_auto") or r.get("marked_paid"))

# Upcoming: not paid, due date not passed. To confirm: recently past due, next statement not in yet.
upcoming = sorted((r for r in rows if r["due"] and not r["paid"] and r["due"] >= today),
                  key=lambda r: r["due"])
confirm  = sorted((r for r in rows if r["due"] and not r["paid"] and r["due"] < today
                   and not r.get("next_stmt_in") and (today - r["due"]).days <= 45),
                  key=lambda r: r["due"])


def _mark_paid(r):
    row = {k: r[k] for k in ("id", "bank", "statement_date", "due_date", "total_due",
                             "paid_auto", "next_stmt_in")}
    row.update(marked_paid=True, updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    service_upsert("card_dues", [row], conflict_col="id")


def _bill(r):
    days = (r["due"] - today).days
    badge = ("Due today" if days == 0 else f"Due in {days} day{'s' if days != 1 else ''}") if days >= 0 \
        else f"{-days} day{'s' if days != -1 else ''} past due"
    colour = "red" if days < 0 else "orange" if days <= 5 else "blue"
    with st.container(border=True):
        # Plain markdown (no st.columns) so the card stays compact on a phone
        st.markdown(f"<div style='display:flex;justify-content:space-between;font-weight:600'>"
                    f"<span>{r['bank']}</span><span>AED {plain_num(r['total_due'])}</span></div>",
                    unsafe_allow_html=True)
        st.markdown(f"Due {r['due']:%a}, {fmt_date(r['due'])} &nbsp; :{colour}-badge[{badge}]")
        if st.button("Mark paid", key=f"paid_{r['id']}", use_container_width=True):
            _mark_paid(r)
            st.rerun()


# ── Still to pay ─────────────────────────────────────────────────────────────
total = sum(float(r["total_due"] or 0) for r in upcoming)
with st.container(border=True):
    st.caption("Still to pay")
    st.markdown(f"### AED {plain_num(total)}")
    if upcoming:
        n, d = len(upcoming), (upcoming[0]["due"] - today).days
        st.caption(f"{n} bill{'s' if n != 1 else ''} · next one "
                   f"{'today' if d == 0 else f'in {d} day' + ('s' if d != 1 else '')}")
    else:
        st.caption("All caught up")

for r in upcoming:
    _bill(r)

if confirm:
    st.subheader("Please confirm")
    st.caption("Due date has passed and the next statement isn't in yet.")
    for r in confirm:
        _bill(r)

# ── Due by month ─────────────────────────────────────────────────────────────
st.subheader("Due by month")
by_month = {}
for r in rows:
    if r["due"] and r.get("total_due") is not None:
        by_month.setdefault((r["due"].year, r["due"].month), []).append(r)

this_month = (today.year, today.month)
for key in sorted(by_month, reverse=True)[:12]:
    bills = sorted(by_month[key], key=lambda r: r["bank"])
    st.markdown(f"<div style='display:flex;justify-content:space-between;border-bottom:1px solid "
                f"rgba(128,128,128,.2);padding:4px 0'>"
                f"<span>{datetime.date(key[0], key[1], 1):%b %Y}</span>"
                f"<span style='font-weight:600'>{plain_num(sum(float(b['total_due']) for b in bills))}</span></div>",
                unsafe_allow_html=True)
    if key >= this_month:
        st.caption(" · ".join(f"{b['bank']} {plain_num(b['total_due'], decimals=0)}" for b in bills))

st.divider()
st.caption(f"Updated from your Mac · {utc_to_ist(max((r['updated_at'] for r in rows), default=None))}")
