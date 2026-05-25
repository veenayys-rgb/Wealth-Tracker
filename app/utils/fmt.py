"""Formatting helpers for Streamlit pages."""
import math, datetime
import pandas as pd


def fmt_date(d) -> str:
    """Convert ISO date string / date object → DD-MMM-YYYY, or '—' if blank."""
    try:
        if not d or str(d).strip() in ("", "—", "None", "nan"):
            return "—"
        if isinstance(d, (datetime.date, datetime.datetime)):
            return d.strftime("%d-%b-%Y")
        return datetime.date.fromisoformat(str(d)[:10]).strftime("%d-%b-%Y")
    except Exception:
        return str(d) or "—"


def parse_date(d) -> datetime.date | None:
    """Safely parse an ISO string or date object → datetime.date, or None."""
    try:
        if not d or str(d).strip() in ("", "—", "None", "nan"):
            return None
        if isinstance(d, datetime.datetime):
            return d.date()
        if isinstance(d, datetime.date):
            return d
        return datetime.date.fromisoformat(str(d)[:10])
    except Exception:
        return None


def ind_num(n, prefix="₹ ", decimals=2) -> str:
    """Format number in Indian system: ₹ 1,00,000.00"""
    if n is None:
        return "—"
    try:
        n = float(n)
        if math.isnan(n):
            return "—"
    except (TypeError, ValueError):
        return "—"
    neg = n < 0
    n = abs(n)
    fmt = f"{n:.{decimals}f}"
    int_p, dec_p = fmt.split(".")
    if len(int_p) <= 3:
        grouped = int_p
    else:
        last3 = int_p[-3:]
        rest = int_p[:-3]
        parts = []
        while rest:
            parts.insert(0, rest[-2:] if len(rest) >= 2 else rest)
            rest = rest[:-2]
        grouped = ",".join(parts) + "," + last3
    result = f"{prefix}{grouped}.{dec_p}"
    return f"-{result}" if neg else result


def plain_num(n, decimals=2) -> str:
    """ind_num without the ₹ prefix — for FCY / non-INR amounts."""
    return ind_num(n, prefix="", decimals=decimals)


def inr(val) -> str:
    return ind_num(val)


def pct(val) -> str:
    try:
        return f"{float(val):+.2f}%"
    except Exception:
        return "—"


def colour(val) -> str:
    try:
        return "color: green" if float(val) >= 0 else "color: red"
    except Exception:
        return ""


def metric_card(label: str, value: str, delta: str = None) -> str:
    """Return an HTML metric card for use with st.markdown(unsafe_allow_html=True)."""
    delta_html = f'<div style="font-size:0.85em;color:{"green" if delta and not delta.startswith("-") else "red"}">{delta}</div>' if delta else ""
    return (
        f'<div style="background:#f0f2f6;border-radius:8px;padding:16px 20px;text-align:center">'
        f'<div style="font-size:0.85em;color:#555;margin-bottom:4px">{label}</div>'
        f'<div style="font-size:1.4em;font-weight:700">{value}</div>'
        f'{delta_html}</div>'
    )


def total_metrics(inv: float, cv: float, label_inv="Total Invested", label_cv="Current Value"):
    """Render a 3-column metric row for portfolio totals."""
    import streamlit as st
    gl  = cv - inv
    ret = (gl / inv * 100) if inv > 0 else 0.0
    c1, c2, c3 = st.columns(3)
    c1.metric(label_inv,    ind_num(inv))
    c2.metric(label_cv,     ind_num(cv))
    c3.metric("Gain / Loss", ind_num(gl), f"{ret:+.2f}%")
