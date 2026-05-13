"""Formatting helpers for Streamlit pages."""
import pandas as pd


def inr(val) -> str:
    """Format number as Indian rupee string."""
    try:
        return f"₹ {float(val):>,.2f}"
    except Exception:
        return "—"


def pct(val) -> str:
    try:
        return f"{float(val):+.2f}%"
    except Exception:
        return "—"


def colour(val) -> str:
    """Return green/red based on positive/negative."""
    try:
        return "color: green" if float(val) >= 0 else "color: red"
    except Exception:
        return ""


def style_gain(df: pd.DataFrame, col: str) -> pd.io.formats.style.Styler:
    """Apply green/red colouring to a gain/loss column."""
    return df.style.applymap(
        lambda v: "color: green" if isinstance(v, (int, float)) and v >= 0
                  else "color: red",
        subset=[col]
    )


def portfolio_pct(val: float, total: float) -> str:
    if total <= 0:
        return "0.00%"
    return f"{val / total * 100:.2f}%"


def metric_card(label: str, value: str, delta: str = ""):
    """Returns HTML for a simple metric card."""
    delta_html = f"<p style='color:{'green' if '+' in delta else 'red'};margin:0'>{delta}</p>" if delta else ""
    return f"""
    <div style='background:#f5f7fa;border-radius:8px;padding:16px;text-align:center'>
        <p style='color:#546e7a;font-size:13px;margin:0'>{label}</p>
        <p style='font-size:22px;font-weight:bold;margin:4px 0'>{value}</p>
        {delta_html}
    </div>"""
