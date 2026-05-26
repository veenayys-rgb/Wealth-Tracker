"""Formatting helpers for Streamlit pages."""
import math
import datetime
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
    parts = fmt.split(".")
    int_p = parts[0]
    dec_p = parts[1] if len(parts) > 1 else ""
    if len(int_p) <= 3:
        grouped = int_p
    else:
        last3 = int_p[-3:]
        rest = int_p[:-3]
        grp = []
        while rest:
            grp.insert(0, rest[-2:] if len(rest) >= 2 else rest)
            rest = rest[:-2]
        grouped = ",".join(grp) + "," + last3
    result = f"{prefix}{grouped}.{dec_p}" if dec_p else f"{prefix}{grouped}"
    return f"-{result}" if neg else result


def indian_axis_ticks(y_min: float, y_max: float, n: int = 6):
    """Return (tickvals, ticktext) for a Plotly y-axis formatted in the Indian number system.

    Generates ~n evenly-spaced, nicely-rounded tick values between y_min and y_max
    and labels each one with ind_num(..., decimals=0).
    """
    if y_max <= y_min:
        return [y_min, y_max], [ind_num(y_min, decimals=0), ind_num(y_max, decimals=0)]
    span = y_max - y_min
    raw_step = span / max(n - 1, 1)
    mag = 10 ** math.floor(math.log10(raw_step))
    step = min([1, 2, 2.5, 5, 10], key=lambda x: abs(x * mag - raw_step)) * mag
    start = math.floor(y_min / step) * step
    ticks, t = [], start
    while t <= y_max + step * 0.01:
        if t >= y_min - step * 0.01:
            ticks.append(round(t, 10))
        t += step
    if not ticks:
        ticks = [y_min, y_max]
    return ticks, [ind_num(t, decimals=0) for t in ticks]


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
