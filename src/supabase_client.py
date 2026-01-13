import os
from supabase import create_client, Client
from typing import Dict, Any, Optional

# Load environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

# Initialize client
supabase: Optional[Client] = None

def get_supabase_client() -> Client:
    global supabase
    if not supabase:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return supabase

async def save_audit_to_supabase(
    audit_id: str,
    business_name: str,
    website_url: str,
    industry: str,
    audit_result: Dict[str, Any],
    is_paid: bool = False
):
    """Save audit to Supabase audits table."""
    client = get_supabase_client()
    
    data = {
        "id": audit_id,
        "business_name": business_name,
        "website_url": website_url,
        "industry": industry,
        "business_age": audit_result.get("businessAge", "Unknown"),
        "overall_score": audit_result.get("overallScore", 0),
        "grade": audit_result.get("grade", "F"),
        "audit_payload": audit_result,
        "is_paid": is_paid
    }
    
    # Supabase-py is synchronous by default unless using async client, 
    # but for simplicity/universality we'll wrap or use standard client
    # If using standard client, this is a blocking call. 
    # For high concurrency, we'd want AsyncClient, but standard is fine for now.
    client.table("audits").insert(data).execute()

async def get_audit_from_supabase(audit_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve audit from Supabase."""
    try:
        client = get_supabase_client()
        response = client.table("audits").select("*").eq("id", audit_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Supabase Fetch Error: {e}")
        return None

async def save_lead_to_supabase(email: str, audit_id: str):
    """Save lead to Supabase leads table."""
    try:
        client = get_supabase_client()
        data = {
            "email": email,
            "audit_id": audit_id
        }
        # Upsert if email matches? Or just insert.
        # Unique constraint on email in table might raise error
        client.table("leads").upsert(data, on_conflict="email").execute()
    except Exception as e:
        print(f"Lead Save Error: {e}")

async def mark_audit_paid_in_supabase(audit_id: str) -> bool:
    """Mark an audit as paid in Supabase."""
    try:
        client = get_supabase_client()
        # Update is_paid to True
        response = client.table("audits").update({"is_paid": True}).eq("id", audit_id).execute()
        # Check if any row was updated (response.data should be a list of updated rows)
        if response.data and len(response.data) > 0:
            return True
        return False
    except Exception as e:
        print(f"Supabase Payment Update Error: {e}")
        return False
