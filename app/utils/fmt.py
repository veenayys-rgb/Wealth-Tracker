"""Formatting helpers for Streamlit pages."""
import math
import pandas as pd


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


def total_metrics(inv: float, cv: float, label_inv="Total Invested", label_cv="Current Value"):
    """Render a 3-column metric row for portfolio totals."""
    import streamlit as st
    gl  = cv - inv
    ret = (gl / inv * 100) if inv > 0 else 0.0
    c1, c2, c3 = st.columns(3)
    c1.metric(label_inv,    ind_num(inv))
    c2.metric(label_cv,     ind_num(cv))
    c3.metric("Gain / Loss", ind_num(gl), f"{ret:+.2f}%")
