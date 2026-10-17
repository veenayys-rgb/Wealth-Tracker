"""Monthly nominee digest email.

Email body  — tiny: alert count + summary stats only.
Attachment  — Excel: every asset for every owner, nominee set or not,
              colour-coded (green = complete, amber = not registered, red = missing).

Env vars:
  GMAIL_USER          — sender / reply-to address
  GMAIL_APP_PASSWORD  — 16-char Google App Password
  SUPABASE_URL / SUPABASE_SERVICE_KEY
"""

import os, sys, io, smtplib, datetime, pathlib
from email.mime.text        import MIMEText
from email.mime.multipart   import MIMEMultipart
from email.mime.base        import MIMEBase
from email                  import encoders

import openpyxl
from openpyxl.styles        import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils         import get_column_letter

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from db import get_client

GMAIL_USER         = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
RECIPIENTS         = ["veenayys@gmail.com"]      # expand to family later

_FAMILY     = {"Vinay", "Harsh", "Anusha"}
_ALL_OWNERS = ["Vinay", "Harsh", "Anusha", "Mom"]

# asset_type order shown in spreadsheet
_SECTION_ORDER = ["india_eq", "mf", "bank_india", "bank_uae", "fd", "insurance"]

_SECTION_META = {
    "india_eq":   ("Demat Account",          "DBEAFE", "1E40AF"),
    "mf":         ("Mutual Funds",            "DCFCE7", "15803D"),
    "bank_india": ("Bank Accounts (India)",   "FFEDD5", "C2410C"),
    "bank_uae":   ("Bank Accounts (UAE)",     "FEF9C3", "854D0E"),
    "fd":         ("Fixed Deposits",          "EDE9FE", "5B21B6"),
    "insurance":  ("Insurance",               "FEE2E2", "991B1B"),
}

# ── number format ─────────────────────────────────────────────────────────────

def _ind(v) -> str:
    if v is None: return "—"
    v = float(v)
    if v == 0:   return "—"
    neg = v < 0
    s = f"{abs(v):.0f}"
    if len(s) > 3:
        last3, rest, groups = s[-3:], s[:-3], []
        while rest:
            groups.append(rest[-2:] if len(rest) >= 2 else rest)
            rest = rest[:-2]
        groups.reverse()
        s = ",".join(groups) + "," + last3
    return ("−" if neg else "") + "₹ " + s


# ── data fetch ────────────────────────────────────────────────────────────────

def _fetch_all() -> dict:
    c = get_client()
    nominees  = c.table("cfg_nominees").select("*").execute().data
    eq_hold   = c.table("cfg_equity_india").select("*").execute().data
    eq_prices = {r["symbol"]: float(r["price"])
                 for r in c.table("equity_india_prices").select("symbol,price").execute().data
                 if r.get("symbol")}
    mf_hold   = c.table("cfg_mutual_funds").select("*").execute().data
    mf_nav    = {r["isin"]: float(r["nav"])
                 for r in c.table("mf_navs").select("isin,nav").execute().data}
    bank_in   = c.table("cfg_bank_india").select("*").execute().data
    bank_uae  = c.table("cfg_bank_uae").select("*").execute().data
    fd        = c.table("cfg_fixed_deposits").select("*").execute().data
    insurance = c.table("cfg_insurance").select("*").execute().data
    forex     = {r["pair"]: float(r["rate"])
                 for r in c.table("forex_rates").select("pair,rate").execute().data}
    return dict(nominees=nominees, eq_hold=eq_hold, eq_prices=eq_prices,
                mf_hold=mf_hold, mf_nav=mf_nav, bank_in=bank_in,
                bank_uae=bank_uae, fd=fd, insurance=insurance, forex=forex)


# ── nominee lookup (keyed exactly as Settings.py writes them) ─────────────────

def _nom_index(nominees: list[dict]) -> dict:
    """Returns {(asset_type, asset_ref): [nominee_rows]}."""
    idx: dict = {}
    for n in nominees:
        key = (n.get("asset_type", ""), n.get("asset_ref", ""))
        idx.setdefault(key, []).append(n)
    return idx


# ── asset builders — produce list of (label, balance, asset_ref) per type ────

def _assets_india_eq(owner, eq_hold, eq_prices) -> list[tuple]:
    """One row per owner who has equity holdings."""
    has = any(h.get("owner") == owner for h in eq_hold)
    if not has:
        return []
    total = sum(
        float(h.get("qty", 0)) * eq_prices.get(h.get("symbol", ""), 0.0)
        for h in eq_hold
        if h.get("owner") == owner and h.get("symbol")
    )
    ref = owner
    return [(f"{owner}'s Demat Account", _ind(total) if total else "—", ref)]


def _assets_mf(owner, mf_hold, mf_nav) -> list[tuple]:
    """One row per unique ISIN (same grouping as Settings.py)."""
    seen = {}
    for h in mf_hold:
        if h.get("owner") != owner:
            continue
        raw_isin = h.get("isin", "")
        parts    = raw_isin.rsplit("_", 1)
        folio    = parts[0] if len(parts) == 2 else raw_isin
        isin_key = parts[1] if len(parts) == 2 else raw_isin
        nav      = mf_nav.get(isin_key, 0.0)
        val      = float(h.get("units", 0)) * nav
        ref      = f"{owner}_{folio}"
        label    = h.get("fund_name", folio)
        seen[ref] = seen.get(ref, {"label": label, "val": 0.0})
        seen[ref]["val"] += val
    return [(v["label"], _ind(v["val"]) if v["val"] else "—", r)
            for r, v in sorted(seen.items())]


def _assets_bank_india(owner, bank_in) -> list[tuple]:
    rows = [b for b in bank_in if b.get("owner") == owner]
    result = []
    for b in rows:
        bname = b.get("bank_name", "")
        acc   = b.get("account_no_last4", "")
        ref   = f"{owner}|{bname}|{acc}"
        bal   = b.get("balance") or 0
        cur   = b.get("currency", "INR")
        bal_s = _ind(bal) if cur == "INR" else f"{cur} {bal:,.2f}"
        result.append((f"{bname} …{acc}", bal_s, ref))
    return result


def _assets_bank_uae(owner, bank_uae, aed_inr) -> list[tuple]:
    rows = [b for b in bank_uae if b.get("owner") == owner]
    result = []
    for b in rows:
        bname = b.get("bank_name", "")
        acc   = b.get("account_no", "")
        ref   = f"{owner}|{bname}|{acc}"
        aed   = float(b.get("balance_aed") or 0)
        inr   = aed * aed_inr
        bal_s = f"AED {aed:,.0f} ({_ind(inr)})" if aed else "—"
        result.append((f"{bname} {acc}", bal_s, ref))
    return result


def _assets_fd(owner, fd) -> list[tuple]:
    rows = [f for f in fd if f.get("owner") == owner]
    result = []
    for f in rows:
        bank  = f.get("bank", "")
        fd_no = f.get("fd_no", "")
        ref   = f"{owner}|{bank}|{fd_no}"
        amt   = f.get("amount") or 0
        result.append((f"{bank} {fd_no}", _ind(amt) if amt else "—", ref))
    return result


def _assets_insurance(owner, insurance) -> list[tuple]:
    rows = [i for i in insurance if i.get("owner") == owner]
    result = []
    for i in rows:
        company  = i.get("company_name", "")
        policy   = i.get("policy_no", "")
        ref      = f"{owner}|{policy}"
        iv       = float(i.get("insured_value") or 0)
        cur      = i.get("currency", "INR")
        bal_s    = (_ind(iv) if cur == "INR" else f"{cur} {iv:,.0f}") if iv else "—"
        result.append((f"{company} {policy}".strip(), bal_s, ref))
    return result


# ── Excel builder ─────────────────────────────────────────────────────────────

def _fill(hex6: str) -> PatternFill:
    return PatternFill("solid", fgColor=hex6)

def _font(bold=False, color="000000", size=10) -> Font:
    return Font(bold=bold, color=color, size=size, name="Arial")

def _border() -> Border:
    s = Side(style="thin", color="D1D5DB")
    return Border(left=s, right=s, top=s, bottom=s)

def _build_excel(data: dict) -> bytes:
    wb  = openpyxl.Workbook()
    ws  = wb.active
    ws.title = "Nominee Digest"

    aed_inr   = data["forex"].get("AED_INR", 22.5)
    nom_idx   = _nom_index(data["nominees"])
    today_str = datetime.date.today().strftime("%d %b %Y")

    # Column headers (written later per section)
    COL_HEADERS = ["Asset / Account", "Balance / Value",
                   "Nominee", "Relationship", "%", "Registered", "Notes"]
    COL_WIDTHS  = [38, 22, 20, 16, 6, 10, 32]

    # Set column widths
    for i, w in enumerate(COL_WIDTHS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    row = 1

    # Title row
    ws.merge_cells(f"A{row}:G{row}")
    c = ws.cell(row=row, column=1,
                value=f"Wealth Tracker — Nominee Digest   |   {today_str}")
    c.font      = Font(bold=True, size=13, color="FFFFFF", name="Arial")
    c.fill      = _fill("1E293B")
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[row].height = 24
    row += 1

    # Alerts row
    total_assets = sum(
        len(_assets_india_eq(o, data["eq_hold"], data["eq_prices"])) +
        len(_assets_mf(o, data["mf_hold"], data["mf_nav"])) +
        len(_assets_bank_india(o, data["bank_in"])) +
        (len(_assets_bank_uae(o, data["bank_uae"], aed_inr)) if o in _FAMILY else 0) +
        len(_assets_fd(o, data["fd"])) +
        len(_assets_insurance(o, data["insurance"]))
        for o in _ALL_OWNERS
    )

    all_refs = []
    for o in _ALL_OWNERS:
        for at, getter in [
            ("india_eq",  lambda o=o: _assets_india_eq(o, data["eq_hold"], data["eq_prices"])),
            ("mf",        lambda o=o: _assets_mf(o, data["mf_hold"], data["mf_nav"])),
            ("bank_india",lambda o=o: _assets_bank_india(o, data["bank_in"])),
            ("bank_uae",  lambda o=o: _assets_bank_uae(o, data["bank_uae"], aed_inr) if o in _FAMILY else []),
            ("fd",        lambda o=o: _assets_fd(o, data["fd"])),
            ("insurance", lambda o=o: _assets_insurance(o, data["insurance"])),
        ]:
            for _, _, ref in getter():
                noms = nom_idx.get((at, ref), [])
                has_nom = any((n.get("nominee_name") or "").strip() for n in noms)
                all_registered = all(n.get("nomination_registered") for n in noms if (n.get("nominee_name") or "").strip())
                all_refs.append((o, at, ref, has_nom, all_registered if noms else False))

    missing_nom = sum(1 for *_, has, _ in all_refs if not has)
    not_reg     = sum(1 for *_, has, reg in all_refs if has and not reg)
    complete    = sum(1 for *_, has, reg in all_refs if has and reg)

    ws.merge_cells(f"A{row}:G{row}")
    alert_txt = (
        f"✓ Complete: {complete}    "
        f"⚠ Not Registered: {not_reg}    "
        f"✗ Nominee Missing: {missing_nom}    "
        f"Total Assets: {total_assets}"
    )
    c = ws.cell(row=row, column=1, value=alert_txt)
    c.font      = Font(bold=True, size=10, color="1E293B", name="Arial")
    c.fill      = _fill("F1F5F9")
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[row].height = 18
    row += 1

    # ── per-owner sections ────────────────────────────────────────────────────
    for owner in _ALL_OWNERS:

        # Owner header
        row += 1
        ws.merge_cells(f"A{row}:G{row}")
        c = ws.cell(row=row, column=1, value=f"  {owner}")
        c.font      = Font(bold=True, size=12, color="FFFFFF", name="Arial")
        c.fill      = _fill("334155")
        c.alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[row].height = 22
        row += 1

        section_builders = [
            ("india_eq",   _assets_india_eq(owner, data["eq_hold"], data["eq_prices"])),
            ("mf",         _assets_mf(owner, data["mf_hold"], data["mf_nav"])),
            ("bank_india", _assets_bank_india(owner, data["bank_in"])),
            ("bank_uae",   _assets_bank_uae(owner, data["bank_uae"], aed_inr) if owner in _FAMILY else []),
            ("fd",         _assets_fd(owner, data["fd"])),
            ("insurance",  _assets_insurance(owner, data["insurance"])),
        ]

        for at, assets in section_builders:
            if not assets:
                continue

            title, bg, fg = _SECTION_META[at]

            # Section header
            ws.merge_cells(f"A{row}:G{row}")
            c = ws.cell(row=row, column=1, value=f"  {title}")
            c.font      = Font(bold=True, size=10, color=fg, name="Arial")
            c.fill      = _fill(bg)
            c.alignment = Alignment(horizontal="left", vertical="center")
            ws.row_dimensions[row].height = 18
            row += 1

            # Column header row
            for col, hdr in enumerate(COL_HEADERS, 1):
                c = ws.cell(row=row, column=col, value=hdr)
                c.font      = Font(bold=True, size=9, color="6B7280", name="Arial")
                c.fill      = _fill("F9FAFB")
                c.alignment = Alignment(horizontal="center" if col >= 5 else "left",
                                        vertical="center")
                c.border    = _border()
            ws.row_dimensions[row].height = 16
            row += 1

            for label, bal, ref in assets:
                noms = nom_idx.get((at, ref), [])

                if not noms:
                    # No nominee at all → one red row
                    _write_data_row(ws, row, label, bal, "— not set —", "", "", False, "", at)
                    row += 1
                else:
                    for n in noms:
                        name = (n.get("nominee_name") or "").strip()
                        rel  = (n.get("relationship") or "").strip()
                        pct  = float(n.get("share_pct") or 0)
                        reg  = bool(n.get("nomination_registered"))
                        notes = (n.get("notes") or "").strip()
                        _write_data_row(ws, row, label, bal, name, rel, pct, reg, notes, at)
                        row += 1

    ws.freeze_panes = "A4"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def _write_data_row(ws, row, label, bal, name, rel, pct, reg, notes, at):
    name_s = name if name else "— not set —"
    missing = (not name) or (name == "— not set —")
    not_reg = name and not reg and at != "insurance"

    if missing:
        fill = _fill("FEE2E2")   # red
    elif not_reg:
        fill = _fill("FFF3CD")   # amber
    else:
        fill = _fill("F0FDF4")   # green

    vals = [label, bal, name_s, rel,
            f"{pct:.0f}%" if pct else "",
            "✓" if reg else ("✗" if name_s != "— not set —" else ""),
            notes]

    for col, val in enumerate(vals, 1):
        c = ws.cell(row=row, column=col, value=val)
        c.fill      = fill
        c.border    = _border()
        c.font      = Font(size=9, name="Arial",
                           color=("DC2626" if col == 3 and missing else "111827"))
        c.alignment = Alignment(
            horizontal="right" if col in (2, 5) else "center" if col == 6 else "left",
            vertical="center", wrap_text=(col == 7)
        )
    ws.row_dimensions[row].height = 15


# ── email body (tiny) ─────────────────────────────────────────────────────────

def _build_body(data: dict) -> str:
    aed_inr = data["forex"].get("AED_INR", 22.5)
    nom_idx = _nom_index(data["nominees"])
    month   = datetime.date.today().strftime("%B %Y")

    counts = {"missing": 0, "not_reg": 0, "complete": 0, "total": 0}
    for o in _ALL_OWNERS:
        for at, getter in [
            ("india_eq",  lambda o=o: _assets_india_eq(o, data["eq_hold"], data["eq_prices"])),
            ("mf",        lambda o=o: _assets_mf(o, data["mf_hold"], data["mf_nav"])),
            ("bank_india",lambda o=o: _assets_bank_india(o, data["bank_in"])),
            ("bank_uae",  lambda o=o: _assets_bank_uae(o, data["bank_uae"], aed_inr) if o in _FAMILY else []),
            ("fd",        lambda o=o: _assets_fd(o, data["fd"])),
            ("insurance", lambda o=o: _assets_insurance(o, data["insurance"])),
        ]:
            for _, _, ref in getter():
                counts["total"] += 1
                noms     = nom_idx.get((at, ref), [])
                has_nom  = any((n.get("nominee_name") or "").strip() for n in noms)
                all_reg  = all(n.get("nomination_registered") for n in noms if (n.get("nominee_name") or "").strip())
                if not has_nom:
                    counts["missing"] += 1
                elif not all_reg:
                    counts["not_reg"] += 1
                else:
                    counts["complete"] += 1

    alert_line = ""
    if counts["missing"] or counts["not_reg"]:
        parts = []
        if counts["missing"]: parts.append(f"{counts['missing']} missing nominee")
        if counts["not_reg"]: parts.append(f"{counts['not_reg']} not registered")
        alert_line = f"⚠️  Action needed: {', '.join(parts)}.<br><br>"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;font-size:14px;color:#1e293b;padding:24px;">

  <h2 style="margin:0 0 8px;">&#x1F4B0; Nominee Digest — {month}</h2>

  <p style="margin:0 0 16px;color:#64748b;">
    Generated {datetime.date.today().strftime('%d %b %Y')}
  </p>

  <table style="border-collapse:collapse;width:280px;">
    <tr>
      <td style="padding:6px 12px;background:#F0FDF4;border:1px solid #D1FAE5;font-weight:700;color:#15803d;">✓ Complete</td>
      <td style="padding:6px 12px;background:#F0FDF4;border:1px solid #D1FAE5;color:#15803d;">{counts['complete']}</td>
    </tr>
    <tr>
      <td style="padding:6px 12px;background:#FFF3CD;border:1px solid #FDE68A;font-weight:700;color:#854d0e;">⚠ Not Registered</td>
      <td style="padding:6px 12px;background:#FFF3CD;border:1px solid #FDE68A;color:#854d0e;">{counts['not_reg']}</td>
    </tr>
    <tr>
      <td style="padding:6px 12px;background:#FEE2E2;border:1px solid #FECACA;font-weight:700;color:#991b1b;">✗ Nominee Missing</td>
      <td style="padding:6px 12px;background:#FEE2E2;border:1px solid #FECACA;color:#991b1b;">{counts['missing']}</td>
    </tr>
    <tr>
      <td style="padding:6px 12px;background:#F1F5F9;border:1px solid #E2E8F0;font-weight:700;color:#334155;">Total Assets</td>
      <td style="padding:6px 12px;background:#F1F5F9;border:1px solid #E2E8F0;color:#334155;">{counts['total']}</td>
    </tr>
  </table>

  <p style="margin:20px 0 0;color:#64748b;font-size:13px;">
    Full details in the attached Excel file.
  </p>

  <p style="margin:24px 0 0;font-size:11px;color:#94a3b8;">
    Sent by Wealth Tracker &nbsp;·&nbsp; Do not reply
  </p>

</body></html>"""


# ── entry point ────────────────────────────────────────────────────────────────

def send_email():
    data     = _fetch_all()
    body     = _build_body(data)
    xl_bytes = _build_excel(data)
    month    = datetime.date.today().strftime("%B %Y")
    filename = f"nominee_digest_{datetime.date.today().strftime('%Y_%m')}.xlsx"

    msg            = MIMEMultipart("mixed")
    msg["Subject"] = f"\U0001F4B0 Nominee Digest — {month}"
    msg["From"]    = GMAIL_USER
    msg["To"]      = ", ".join(RECIPIENTS)

    msg.attach(MIMEText(body, "html"))

    part = MIMEBase("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    part.set_payload(xl_bytes)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
    msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_USER, RECIPIENTS, msg.as_string())

    print(f"✅  Nominee digest sent to: {', '.join(RECIPIENTS)}")
    print(f"   Attachment: {filename}  ({len(xl_bytes):,} bytes)")


if __name__ == "__main__":
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("❌  Set GMAIL_USER and GMAIL_APP_PASSWORD env vars")
        sys.exit(1)
    send_email()
