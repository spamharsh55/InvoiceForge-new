from datetime import datetime
from typing import List, Dict, Any

def format_date_ddmmyyyy(date_str: str) -> str:
    """Formats a YYYY-MM-DD date string to DD-MM-YYYY."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except (ValueError, TypeError):
        return date_str or ""

def to_number(val: Any) -> float:
    """Safely converts a value to a float, returning 0.0 on failure."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0

def compute_total_from_charges(charges: List[Dict[str, Any]]) -> float:
    """Calculates the total amount from a list of charge dictionaries."""
    return round(sum(to_number(ch.get("amount", 0)) for ch in (charges or [])), 2)

def normalize_charges_from_request(form) -> List[Dict[str, Any]]:
    """
    Parses Flask request form data for charges and returns a list of dictionaries.
    Filters out empty rows.
    """
    types = form.getlist("charge_type[]")
    amounts = form.getlist("charge_amount[]")
    remarks = form.getlist("charge_remark[]")
    charges = []
    for t, a, r in zip(types, amounts, remarks):
        t = (t or "").strip()
        if not t and not (a or "").strip() and not (r or "").strip():
            continue
        amt = to_number(a)
        charges.append({"type": t, "amount": amt, "remark": r or ""})
    return charges