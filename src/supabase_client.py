import os
from supabase import create_client, Client
from typing import Dict, Any, Optional, Tuple
from fastapi import HTTPException

# Initialize client
supabase: Optional[Client] = None

def _get_supabase_settings() -> Tuple[str, str]:
    url = os.environ.get("SUPABASE_URL") or os.environ.get("SUPABASE_PROJECT_URL")
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY")
        or os.environ.get("SUPABASE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
    )

    missing = []
    if not url:
        missing.append("SUPABASE_URL")
    if not key:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")

    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(
            f"Missing Supabase env var(s): {missing_list}. "
            "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )

    return url, key


def get_supabase_client() -> Client:
    global supabase
    if not supabase:
        url, key = _get_supabase_settings()
        supabase = create_client(url, key)
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
        "audit_payload": audit_result,
        "is_paid": is_paid
    }
    
    # Supabase-py is synchronous by default unless using async client, 
    # but for simplicity/universality we'll wrap or use standard client
    # If using standard client, this is a blocking call. 
    # For high concurrency, we'd want AsyncClient, but standard is fine for now.
    res = client.table("audits").insert(data).execute()
    
    print("SUPABASE INSERT RESPONSE:", res)
    
    # Check for error (handling both APIError raise and response.error property if present)
    error = getattr(res, "error", None)
    if error:
        print("SUPABASE ERROR:", error)
        raise HTTPException(status_code=500, detail="Audit persistence failed")

    if getattr(res, "data", None) is None:
        raise HTTPException(status_code=500, detail="Audit persistence failed")

async def get_audit_from_supabase(audit_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve audit from Supabase."""
    client = get_supabase_client()
    response = client.table("audits").select("*").eq("id", audit_id).execute()
    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Supabase fetch failed: {error}")
    if response.data:
        return response.data[0]
    return None

async def save_lead_to_supabase(email: str, audit_id: str):
    """Save lead to Supabase leads table."""
    client = get_supabase_client()
    data = {
        "email": email,
        "audit_id": audit_id
    }
    
    print(f"SAVING LEAD: email={email}, audit_id={audit_id}")

    try:
        response = client.table("leads_new").insert(data).execute()
        print("SUPABASE LEAD INSERT RESPONSE:", response)
    except Exception as e:
        message = str(e)
        print(f"SUPABASE LEAD INSERT EXCEPTION: {message}")
        if "duplicate" in message.lower():
            print("Lead already exists (duplicate), skipping.")
            return
        raise HTTPException(status_code=500, detail=f"Lead persistence failed: {message}")

    error = getattr(response, "error", None)
    if error:
        message = str(error)
        print(f"SUPABASE LEAD INSERT ERROR: {message}")
        if "duplicate" in message.lower():
            print("Lead already exists (duplicate), skipping.")
            return
        raise HTTPException(status_code=500, detail=f"Lead persistence failed: {message}")

    if getattr(response, "data", None) is None:
        print("SUPABASE LEAD INSERT: No data returned!")
        raise HTTPException(status_code=500, detail="Lead persistence failed")

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
