from supabase import Client
from typing import List, Dict, Any
from .helpers import to_number

def insert_record(supabase: Client, data: Dict[str, Any]):
    """Inserts a new record into the 'pdf_records' table."""
    payload = {
        "name": data.get("name"),
        "date": data.get("date"),
        "from_date": data.get("from_date"),
        "to_date": data.get("to_date"),
        "charges": data.get("charges"),
        "total": data.get("total"),
    }
    return supabase.table("pdf_records").insert(payload).execute()

def update_record_db(supabase: Client, record_id: int, data: Dict[str, Any]):
    """Updates an existing record in the 'pdf_records' table."""
    payload = {
        "name": data.get("name"),
        "date": data.get("date"),
        "from_date": data.get("from_date"),
        "to_date": data.get("to_date"),
        "charges": data.get("charges"),
        "total": data.get("total"),
    }
    return supabase.table("pdf_records").update(payload).eq("id", record_id).execute()

def fetch_one(supabase: Client, record_id: int) -> Dict[str, Any] | None:
    """Fetches a single record by its ID."""
    res = supabase.table("pdf_records").select("*").eq("id", record_id).single().execute()
    return res.data if res.data else None

def fetch_all(supabase: Client) -> List[Dict[str, Any]]:
    """Fetches all records, ordered by ID descending."""
    res = supabase.table("pdf_records").select("*").order("id", desc=True).execute()
    return res.data or []

def delete_record_db(supabase: Client, record_id: int):
    """Deletes a record from the 'pdf_records' table."""
    return supabase.table("pdf_records").delete().eq("id", record_id).execute()

def migrate_row_to_charges_if_needed(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Backward compatibility helper. Converts old schema rows to the new charges array format.
    """
    if row.get("charges"):
        return row["charges"]
    pairs = [
        ("C & F CHARGES", "cf_charges", "cf_remarks"),
        ("GODOWN RENT", "godown_rent", "godown_remarks"),
        ("COURIER CHARGES", "courier_charges", "courier_remarks"),
        ("ELECTRIC BILL", "electric_bill", "electric_remarks"),
        ("INTERNET CHARGES", "internet_charges", "internet_remarks"),
        ("LOCAL FREIGHT", "local_freight", "local_remarks"),
        ("LABOUR CHARGES", "labour_charges", "labour_remarks"),
        ("HAMALI CHARGES", "hamali_charges", "hamali_remarks"),
    ]
    charges = []
    for label, amount_key, remark_key in pairs:
        amount = row.get(amount_key)
        remark = row.get(remark_key)
        if amount is not None and str(amount).strip() not in ("", "None", "null"):
            charges.append({"type": label, "amount": to_number(amount), "remark": remark or ""})
    return charges