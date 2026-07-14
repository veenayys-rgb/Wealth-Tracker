"""CAMS JSON statement parser → normalized transaction rows."""
import json
import hashlib
import datetime


# All variants found in CAMS exports → canonical type
_TYPE_RULES = [
    ("stp switch in",   "SWITCH_IN"),
    ("switch-in",       "SWITCH_IN"),
    ("switch in",       "SWITCH_IN"),
    ("switch- out",     "SWITCH_OUT"),
    ("switch-out",      "SWITCH_OUT"),
    ("switch out",      "SWITCH_OUT"),
    ("redemption",      "SELL"),
    ("idcw",            "DIVIDEND"),
    ("dividend",        "DIVIDEND"),
    ("purchase",        "BUY"),
    ("sip",             "BUY"),
    ("systematic",      "BUY"),
    ("nfo",             "BUY"),
]


def normalize_txn_type(raw: str) -> str:
    t = raw.strip().lower()
    for fragment, canonical in _TYPE_RULES:
        if fragment in t:
            return canonical
    return "OTHER"


def _parse_date(s: str) -> str | None:
    if not s:
        return None
    try:
        return datetime.datetime.strptime(s.strip(), "%d-%b-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return s.strip()


def _txn_id(r: dict) -> str:
    key = "|".join(str(r.get(k) or "") for k in
                   ("FOLIO_NUMBER", "PRODUCT_CODE", "TRADE_DATE",
                    "UNITS", "AMOUNT", "TRANSACTION_TYPE"))
    return hashlib.md5(key.encode()).hexdigest()


def parse_cams_json(file_bytes: bytes, owner: str, source_file: str
                    ) -> tuple[list[dict], int]:
    """Parse raw CAMS JSON bytes.

    Returns (rows_to_upsert, skipped_non_financial_count).
    Rows with neither UNITS nor AMOUNT are administrative records and are skipped.
    """
    data = json.loads(file_bytes)
    raw_rows = data.get("dtTrxnResult", [])

    result, skipped = [], 0
    for r in raw_rows:
        units  = r.get("UNITS")
        amount = r.get("AMOUNT")

        if units is None and amount is None:
            skipped += 1
            continue

        raw_type = (r.get("TRANSACTION_TYPE") or "").strip()

        result.append({
            "txn_id":       _txn_id(r),
            "folio_number": (r.get("FOLIO_NUMBER") or "").strip(),
            "product_code": (r.get("PRODUCT_CODE") or "").strip(),
            "scheme_name":  (r.get("SCHEME_NAME")  or "").strip(),
            "mf_name":      (r.get("MF_NAME")       or "").strip(),
            "owner":        owner,
            "pan":          (r.get("PAN")           or "").strip(),
            "trade_date":   _parse_date(r.get("TRADE_DATE", "")),
            "txn_type":     normalize_txn_type(raw_type),
            "raw_txn_type": raw_type,
            "units":        float(units)  if units  is not None else None,
            "price":        float(r["PRICE"])  if r.get("PRICE")  is not None else None,
            "amount":       float(amount) if amount is not None else None,
            "fund_type":    (r.get("Type") or "").strip(),
            "broker":       (r.get("BROKER") or "").strip(),
            "source_file":  source_file,
        })

    return result, skipped
