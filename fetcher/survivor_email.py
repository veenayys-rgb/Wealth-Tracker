"""Monthly nominee digest email. Sends to RECIPIENTS via Gmail SMTP.

Env vars required:
  GMAIL_USER          — sender address, e.g. veenayys@gmail.com
  GMAIL_APP_PASSWORD  — 16-char Google App Password (not your Gmail login)
  SUPABASE_URL / SUPABASE_SERVICE_KEY — same as other fetchers
"""

import os, sys, smtplib, datetime, pathlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from db import get_client

GMAIL_USER         = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

# Sending to Vinay only for now; expand to full family later
RECIPIENTS = ["veenayys@gmail.com"]

_FAMILY      = {"Vinay", "Harsh", "Anusha"}
_ALL_OWNERS  = ["Vinay", "Harsh", "Anusha", "Mom"]

_SECTION_ORDER = ["india_eq", "mutual_funds", "bank_india", "bank_uae", "fd", "insurance"]

_CLR = {
    "india_eq":     ("#dbeafe", "#1e40af", "Demat Account"),
    "mutual_funds": ("#dcfce7", "#15803d", "Mutual Funds"),
    "bank_india":   ("#ffedd5", "#c2410c", "Bank Accounts (India)"),
    "bank_uae":     ("#fef9c3", "#854d0e", "Bank Accounts (UAE)"),
    "fd":           ("#ede9fe", "#5b21b6", "Fixed Deposits"),
    "insurance":    ("#fee2e2", "#991b1b", "Insurance"),
}


# ── formatting ────────────────────────────────────────────────────────────────

def _ind(v) -> str:
    """₹ X,XX,XXX  — Indian grouping, no decimals."""
    if v is None:
        return "—"
    v = float(v)
    if v == 0:
        return "—"
    neg = v < 0
    s = f"{abs(v):.0f}"
    if len(s) > 3:
        last3 = s[-3:]
        rest   = s[:-3]
        groups = []
        while rest:
            groups.append(rest[-2:] if len(rest) >= 2 else rest)
            rest = rest[:-2]
        groups.reverse()
        s = ",".join(groups) + "," + last3
    return ("−" if neg else "") + "₹ " + s


# ── data fetching ─────────────────────────────────────────────────────────────

def _fetch_all() -> dict:
    c = get_client()
    nominees   = c.table("cfg_nominees").select("*").execute().data
    eq_hold    = c.table("cfg_equity_india").select("*").execute().data
    eq_prices  = {r["symbol"]: float(r["price"])
                  for r in c.table("equity_india_prices").select("symbol,price").execute().data
                  if r.get("symbol")}
    mf_hold    = c.table("cfg_mutual_funds").select("*").execute().data
    mf_nav     = {r["isin"]: float(r["nav"])
                  for r in c.table("mf_navs").select("isin,nav").execute().data}
    bank_in    = c.table("cfg_bank_india").select("*").execute().data
    bank_uae   = c.table("cfg_bank_uae").select("*").execute().data
    fd         = c.table("cfg_fixed_deposits").select("*").execute().data
    insurance  = c.table("cfg_insurance").select("*").execute().data
    forex      = {r["pair"]: float(r["rate"])
                  for r in c.table("forex_rates").select("pair,rate").execute().data}
    return dict(nominees=nominees, eq_hold=eq_hold, eq_prices=eq_prices,
                mf_hold=mf_hold, mf_nav=mf_nav, bank_in=bank_in,
                bank_uae=bank_uae, fd=fd, insurance=insurance, forex=forex)


# ── balance helpers ────────────────────────────────────────────────────────────

def _equity_cv(owner: str, eq_hold, eq_prices) -> float | None:
    total = sum(
        float(h.get("qty", 0)) * eq_prices.get(h.get("symbol", ""), 0.0)
        for h in eq_hold
        if h.get("owner") == owner and h.get("symbol")
    )
    return total if total > 0 else None


def _mf_folio_cv(folio_no: str, mf_hold, mf_nav) -> float | None:
    total = sum(
        float(h.get("units", 0)) * mf_nav.get(h.get("isin", ""), 0.0)
        for h in mf_hold
        if h.get("folio_no") == folio_no and h.get("isin")
    )
    return total if total > 0 else None


def _balance(asset_type: str, asset_ref: str, owner: str, data: dict) -> str:
    aed_inr = data["forex"].get("AED_INR", 22.5)

    if asset_type == "india_eq":
        cv = _equity_cv(owner, data["eq_hold"], data["eq_prices"])
        return _ind(cv)

    if asset_type == "mutual_funds":
        cv = _mf_folio_cv(asset_ref, data["mf_hold"], data["mf_nav"])
        return _ind(cv)

    if asset_type == "bank_india":
        for b in data["bank_in"]:
            if b.get("account_no_last4") == asset_ref and b.get("owner") == owner:
                bal = b.get("balance") or 0
                cur = b.get("currency", "INR")
                return _ind(bal) if cur == "INR" else f"{cur} {bal:,.2f}"

    if asset_type == "bank_uae":
        for b in data["bank_uae"]:
            if b.get("account_no") == asset_ref and b.get("owner") == owner:
                aed = float(b.get("balance_aed") or 0)
                inr = aed * aed_inr
                return f"AED {aed:,.0f} ({_ind(inr)})"

    if asset_type == "fd":
        for f in data["fd"]:
            if f.get("fd_no") == asset_ref and f.get("owner") == owner:
                return _ind(f.get("amount"))

    if asset_type == "insurance":
        for i in data["insurance"]:
            if i.get("policy_no") == asset_ref and i.get("owner") == owner:
                iv  = float(i.get("insured_value") or 0)
                cur = i.get("currency", "INR")
                if cur == "INR":
                    return _ind(iv)
                return f"{cur} {iv:,.0f}" if iv else "—"

    return "—"


# ── HTML builder ──────────────────────────────────────────────────────────────

_TH = ("padding:7px 10px;border:1px solid #e5e7eb;font-size:12px;"
       "text-align:{align};color:#6b7280;white-space:nowrap;")
_TD = "padding:7px 10px;border:1px solid #e5e7eb;font-size:13px;"


def _th(label: str, align: str = "left") -> str:
    return f'<th style="{_TH.format(align=align)}">{label}</th>'


def _td(content: str, extra: str = "") -> str:
    return f'<td style="{_TD}{extra}">{content}</td>'


def _build_html(data: dict) -> str:
    nominees = data["nominees"]
    today    = datetime.date.today()
    month    = today.strftime("%B %Y")

    # Group nominees: owner → asset_type → [rows]
    by_owner: dict[str, dict] = {o: {} for o in _ALL_OWNERS}
    for n in nominees:
        o  = n.get("owner", "")
        at = n.get("asset_type", "")
        if o in by_owner:
            by_owner[o].setdefault(at, []).append(n)

    # Collect alerts
    alerts = []
    for n in nominees:
        name = (n.get("nominee_name") or "").strip()
        pct  = float(n.get("share_pct") or 0)
        reg  = bool(n.get("nomination_registered"))
        lbl  = (n.get("label") or n.get("asset_ref") or "").strip()
        owner = n.get("owner", "")
        _, _, section_title = _CLR.get(n.get("asset_type", ""), ("", "", n.get("asset_type", "")))
        prefix = f"{owner} — {section_title}: <b>{lbl}</b>"
        if not name:
            alerts.append(f"⚠️ {prefix} has no nominee set")
        elif n.get("asset_type") != "insurance" and pct != 100:
            alerts.append(f"⚠️ {prefix}: nominee % = {pct:.0f}% (expected 100%)")
        if name and not reg:
            alerts.append(f"📋 {prefix}: nomination not registered")

    # Alert block
    alert_html = ""
    if alerts:
        items = "".join(
            f'<li style="margin:4px 0;line-height:1.5;">{a}</li>'
            for a in alerts
        )
        alert_html = (
            '<div style="background:#fff3cd;border:1px solid #ffc107;border-radius:6px;'
            'padding:12px 16px;margin-bottom:20px;">'
            f'<div style="font-weight:700;color:#856404;margin-bottom:6px;">'
            f'⚠️ Action Required ({len(alerts)} item{"s" if len(alerts) != 1 else ""})</div>'
            f'<ul style="margin:0;padding-left:20px;color:#856404;">{items}</ul>'
            '</div>'
        )

    # Owner sections
    owner_sections = ""
    for owner in _ALL_OWNERS:
        owner_html = ""
        for at in _SECTION_ORDER:
            rows = by_owner[owner].get(at, [])
            if not rows:
                continue
            if at == "bank_uae" and owner not in _FAMILY:
                continue

            bg, fg, title = _CLR.get(at, ("#f0f0f0", "#333", at))

            table_rows = ""
            for n in rows:
                name  = (n.get("nominee_name") or "").strip()
                rel   = (n.get("relationship") or "").strip() or "—"
                pct   = float(n.get("share_pct") or 0)
                reg   = n.get("nomination_registered", False)
                notes = (n.get("notes") or "").strip() or "—"
                lbl   = (n.get("label") or n.get("asset_ref") or "").strip()
                bal   = _balance(at, n.get("asset_ref", ""), owner, data)

                name_color  = "#dc2626" if not name else "#111827"
                name_display = name if name else "— not set —"
                reg_mark    = "✓" if reg else "✗"
                reg_color   = "#16a34a" if reg else "#dc2626"

                table_rows += (
                    "<tr>"
                    + _td(lbl, "color:#111827;")
                    + _td(name_display, f"color:{name_color};")
                    + _td(rel, "color:#555;")
                    + _td(f"{pct:.0f}%", "text-align:right;")
                    + _td(reg_mark, f"text-align:center;font-weight:700;color:{reg_color};")
                    + _td(bal, "text-align:right;font-family:monospace;font-size:12px;")
                    + _td(notes, "color:#555;font-size:12px;")
                    + "</tr>"
                )

            owner_html += (
                f'<div style="background:{bg};color:{fg};padding:7px 14px;font-weight:600;'
                f'font-size:13px;border-radius:4px;margin:10px 0 0 0;">{title}</div>'
                '<table style="width:100%;border-collapse:collapse;margin-bottom:4px;">'
                "<thead><tr style='background:#f9fafb;'>"
                + _th("Asset") + _th("Nominee") + _th("Relationship")
                + _th("%", "right") + _th("Reg", "center")
                + _th("Balance / Value", "right") + _th("Notes")
                + "</tr></thead>"
                f"<tbody>{table_rows}</tbody>"
                "</table>"
            )

        if owner_html:
            owner_sections += (
                '<div style="margin-bottom:28px;">'
                f'<h2 style="font-size:15px;font-weight:700;color:#1e293b;'
                f'border-bottom:2px solid #e2e8f0;padding-bottom:6px;margin:0 0 2px 0;">'
                f'{owner}</h2>'
                f'{owner_html}'
                '</div>'
            )

    # Summary stats
    total_assets   = len(nominees)
    nominees_set   = sum(1 for n in nominees if (n.get("nominee_name") or "").strip())
    reg_done       = sum(1 for n in nominees if n.get("nomination_registered"))
    actions_needed = len(alerts)

    summary = (
        '<div style="background:#f1f5f9;border-radius:6px;padding:14px 18px;margin-top:8px;">'
        '<span style="font-size:13px;color:#475569;">'
        f'<b>Assets tracked:</b> {total_assets} &nbsp;|&nbsp; '
        f'<b>Nominees set:</b> {nominees_set}/{total_assets} &nbsp;|&nbsp; '
        f'<b>Registered:</b> {reg_done}/{total_assets} &nbsp;|&nbsp; '
        f'<b>Actions needed:</b> {actions_needed}'
        '</span></div>'
    )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Nominee Digest — {month}</title></head>
<body style="font-family:Arial,Helvetica,sans-serif;margin:0;padding:0;background:#f8fafc;">
<div style="max-width:820px;margin:0 auto;padding:24px 16px;">

  <div style="background:#1e293b;color:#fff;padding:20px 24px;border-radius:8px;margin-bottom:20px;">
    <div style="font-size:20px;font-weight:700;">&#x1F4B0; Wealth Tracker — Nominee Digest</div>
    <div style="font-size:13px;color:#94a3b8;margin-top:4px;">{month} &nbsp;··· Generated {today.strftime('%d %b %Y')}</div>
  </div>

  {alert_html}
  {owner_sections}
  {summary}

  <div style="font-size:11px;color:#94a3b8;text-align:center;margin-top:16px;">
    Sent by Wealth Tracker &nbsp;·&nbsp; Do not reply
  </div>

</div>
</body>
</html>"""


# ── entry point ────────────────────────────────────────────────────────────────

def send_email():
    data  = _fetch_all()
    html  = _build_html(data)
    month = datetime.date.today().strftime("%B %Y")

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = f"\U0001F4B0 Nominee Digest — {month}"
    msg["From"]    = GMAIL_USER
    msg["To"]      = ", ".join(RECIPIENTS)
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_USER, RECIPIENTS, msg.as_string())

    print(f"✅  Nominee digest sent to: {', '.join(RECIPIENTS)}")


if __name__ == "__main__":
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("❌  Set GMAIL_USER and GMAIL_APP_PASSWORD env vars")
        sys.exit(1)
    send_email()
