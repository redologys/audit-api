"""
FastAPI REST API for Business Digital Presence Audit.
"""
import os
import uuid
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, EmailStr
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .input_handler import BusinessInput, validate_business_input, format_input_for_groq
from .groq_client import GroqAuditClient, GroqClientError
from .score_validator import validate_audit_result, correct_audit_scores
from .supabase_client import (
    save_audit_to_supabase, get_audit_from_supabase, 
    save_lead_to_supabase, mark_audit_paid_in_supabase
)
from .database import track_api_usage, check_rate_limit

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create FastAPI app
app = FastAPI(
    title="Business Digital Presence Audit API",
    description="AI-powered business audit using Groq LLM",
    version="2.0.0"
)

# Add rate limit error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration - parse from environment
raw_origins = os.getenv("CORS_ORIGINS", "")
origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

# In production, NEVER use wildcard - use explicit origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Initialize Groq client
groq_client = None

def get_groq_client():
    global groq_client
    if groq_client is None:
        groq_client = GroqAuditClient()
    return groq_client


# Request/Response Models
class AuditRequest(BaseModel):
    business_name: str
    website_url: Optional[str] = None
    industry: str = "unknown"
    location: str = "unknown"
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    tiktok: Optional[str] = None
    twitter: Optional[str] = None
    linkedin: Optional[str] = None
    youtube: Optional[str] = None
    business_age: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None


class AuditResponse(BaseModel):
    audit_id: str
    overall_score: int
    grade: str
    executive_summary: str
    category_breakdown: dict
    quick_wins: list
    free_report_sections: list
    upgrade_cta: str


class LeadRequest(BaseModel):
    audit_id: str
    email: EmailStr

class ReportRequest(BaseModel):
    audit_id: str
    report_type: str = "free"  # "free" or "paid"
    email: Optional[EmailStr] = None


# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/")
def healthcheck_root():
    return {"status": "ok"}


# Main audit endpoint
@app.post("/api/audit", response_model=AuditResponse)
@limiter.limit("10/hour")
async def create_audit(request: Request, audit_request: AuditRequest):
    """
    Generate a business digital presence audit.
    
    Rate limited to 10 requests per hour per IP for free tier.
    """
    client_ip = get_remote_address(request)
    
    # Track API usage
    await track_api_usage(client_ip, "/api/audit")
    
    try:
        # Validate and format input
        input_data = audit_request.model_dump()
        validated_input = validate_business_input(input_data)
        groq_input = format_input_for_groq(validated_input)
        
        # Call Groq API
        client = get_groq_client()
        audit_result = await client.generate_audit(groq_input)
        
        # Validate scores
        validation = validate_audit_result(audit_result)
        if not validation.is_valid:
            # Try to correct minor issues
            audit_result = correct_audit_scores(audit_result)
        
        # Generate audit ID
        audit_id = str(uuid.uuid4())
        
        # Save to Supabase (Persistent)
        try:
            # Save audit payload
            await save_audit_to_supabase(
                audit_id=audit_id,
                business_name=validated_input.business_name,
                website_url=validated_input.website_url,
                industry=validated_input.industry,
                audit_result=audit_result
            )
            # Save lead email
            if validated_input.email:
                await save_lead_to_supabase(validated_input.email, audit_id)
                
        except Exception as e:
            print(f"Supabase Save Error: {e}")
            # Ensure we still return result even if save fails temporarily
            pass
        
        # Format response
        return AuditResponse(
            audit_id=audit_id,
            overall_score=audit_result.get('overallScore', 0),
            grade=audit_result.get('grade', 'F'),
            executive_summary=audit_result.get('executiveSummary', ''),
            category_breakdown=audit_result.get('categoryBreakdown', {}),
            quick_wins=audit_result.get('quickWins', [])[:3],  # Top 3 for free
            free_report_sections=audit_result.get('freeReport', {}).get('includedSections', []),
            upgrade_cta=audit_result.get('freeReport', {}).get('callToAction', 
                'Unlock your complete growth roadmap with detailed strategies')
        )
        
    except GroqClientError as e:
        raise HTTPException(status_code=503, detail=f"AI service error: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# Get audit by ID
@app.get("/api/audit/{audit_id}")
async def get_audit(audit_id: str):
    """Retrieve a previous audit by ID."""
    audit = await get_audit_from_supabase(audit_id)
    
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    
    # Return full result for paid, limited for free
    if audit['is_paid']:
        return audit['audit_payload']
    else:
        # Return limited free version
        result = audit['audit_payload']
        return {
            'audit_id': audit_id,
            'overall_score': result.get('overallScore'),
            'grade': result.get('grade'),
            'executive_summary': result.get('executiveSummary'),
            'category_breakdown': {
                k: {'score': v.get('score'), 'maxPoints': v.get('maxPoints')}
                for k, v in result.get('categoryBreakdown', {}).items()
            },
            'quick_wins': result.get('quickWins', [])[:3],
            'top_strengths': result.get('topStrengths', [])[:2],
            'critical_weaknesses': result.get('criticalWeaknesses', [])[:2],
            'is_paid': False,
            'upgrade_available': True
        }


# Capture Lead Endpoint
@app.post("/api/lead")
async def capture_lead(lead_request: LeadRequest):
    """
    Capture a lead (email) for a specific audit.
    Useful for gated content or follow-ups.
    """
    try:
        await save_lead_to_supabase(lead_request.email, lead_request.audit_id)
        return {"success": True}
    except Exception as e:
        # Log but don't fail the request significantly (optional: return 500)
        print(f"Lead capture error: {e}")
        return {"success": False, "error": str(e)}


# Generate PDF report
@app.post("/api/generate-report")
async def generate_report(report_request: ReportRequest):
    """Generate PDF report for an audit."""
    # Retrieve from Supabase
    audit = await get_audit_from_supabase(report_request.audit_id)
    
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    
    # Check if paid report is requested
    LOGIC_TEST_MODE = os.getenv("LOGIC_TEST_MODE", "false").lower() == "true"
    
    if report_request.report_type == "paid" and not audit['is_paid']:
        if LOGIC_TEST_MODE:
            print(f"TEST MODE: Allowing paid report generation for audit {report_request.audit_id}")
        else:
            raise HTTPException(
                status_code=402, 
                detail="Payment required for full report. Please complete purchase first."
            )
    
    try:
        # Import here to avoid loading at startup
        from .report_generator import generate_pdf_report
        
        report_path = await generate_pdf_report(
            audit_id=report_request.audit_id,
            audit_data=audit['audit_payload'],
            business_name=audit['business_name'],
            report_type=report_request.report_type
        )
        
        # Determine media type based on file extension
        if report_path.endswith('.pdf'):
            media_type = "application/pdf"
            filename = f"audit-report-{report_request.audit_id}.pdf"
        else:
            media_type = "text/html"
            filename = f"audit-report-{report_request.audit_id}.html"
        
        return FileResponse(
            report_path,
            media_type=media_type,
            filename=filename
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


# Get full audit result (requires API key or paid status)
@app.get("/api/audit/{audit_id}/full")
async def get_full_audit(audit_id: str, api_key: Optional[str] = None):
    """Get full audit result including all details."""
    audit = await get_audit_from_supabase(audit_id)
    
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    
    # Check authorization
    admin_key = os.getenv("ADMIN_API_KEY")
    if not audit['is_paid'] and api_key != admin_key:
        raise HTTPException(
            status_code=403, 
            detail="Full audit requires payment or admin access"
        )
    
    return audit['audit_payload']


# Rate limit status endpoint
@app.get("/api/rate-limit-status")
async def rate_limit_status(request: Request):
    """Check current rate limit status for the client."""
    client_ip = get_remote_address(request)
    is_allowed, remaining = await check_rate_limit(client_ip)
    
    return {
        "allowed": is_allowed,
        "remaining": remaining,
        "limit": 10,
        "window": "1 hour"
    }


# Error handlers
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": "You have exceeded the free tier limit of 10 audits per hour.",
            "upgrade_message": "Upgrade to Pro for unlimited audits."
        }
    )


# ============================================
# TEST MODE ENDPOINTS
# ============================================

LOGIC_TEST_MODE = os.getenv("LOGIC_TEST_MODE", "false").lower() == "true"


class CheckoutRequest(BaseModel):
    audit_id: str
    email: Optional[EmailStr] = None


class PaymentConfirmRequest(BaseModel):
    audit_id: str
    session_id: Optional[str] = None
    payment_intent_id: Optional[str] = None


# Test mode audit endpoint (no Groq)
@app.post("/api/test-audit", response_model=AuditResponse)
async def create_test_audit(request: Request, audit_request: AuditRequest):
    """
    Generate a test audit with mock data (no Groq call).
    Always available for testing logic flow.
    """
    client_ip = get_remote_address(request)
    await track_api_usage(client_ip, "/api/test-audit")
    
    try:
        from .mock_data import generate_mock_audit
        
        # Generate mock audit
        audit_result = generate_mock_audit(
            business_name=audit_request.business_name,
            industry=audit_request.industry
        )
        
        # Generate audit ID
        audit_id = f"test-{str(uuid.uuid4())[:6]}"
        
        # Save to database with test flag
        await save_audit(
            audit_id=audit_id,
            business_name=audit_request.business_name,
            input_data=audit_request.model_dump(),
            audit_result=audit_result,
            website_url=audit_request.website_url,
            industry=audit_request.industry,
            location=audit_request.location,
            email=str(audit_request.email) if audit_request.email else None,
            is_test=True
        )
        
        return AuditResponse(
            audit_id=audit_id,
            overall_score=audit_result.get('overallScore', 0),
            grade=audit_result.get('grade', 'F'),
            executive_summary=audit_result.get('executiveSummary', ''),
            category_breakdown=audit_result.get('categoryBreakdown', {}),
            quick_wins=audit_result.get('quickWins', [])[:3],
            free_report_sections=audit_result.get('freeReport', {}).get('includedSections', []),
            upgrade_cta=audit_result.get('freeReport', {}).get('callToAction', 
                'Unlock your complete growth roadmap')
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test audit error: {str(e)}")


# Test mode report generation
@app.post("/api/test-generate-report")
async def generate_test_report(report_request: ReportRequest):
    """Generate report in test mode (allows both free and paid without payment)."""
    audit = await get_audit_from_supabase(report_request.audit_id)
    
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    
    try:
        from .report_generator import generate_pdf_report
        
        # In test mode, allow full report without payment
        report_path = await generate_pdf_report(
            audit_id=report_request.audit_id,
            audit_data=audit['audit_payload'],
            business_name=audit['business_name'],
            report_type=report_request.report_type
        )
        
        # Determine media type
        if report_path.endswith('.pdf'):
            media_type = "application/pdf"
            filename = f"audit-report-{report_request.audit_id}.pdf"
        else:
            media_type = "text/html"
            filename = f"audit-report-{report_request.audit_id}.html"
        
        return FileResponse(
            report_path,
            media_type=media_type,
            filename=filename
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Test report error: {str(e)}")


# ============================================
# PAYMENT / CHECKOUT ENDPOINTS
# ============================================

@app.post("/api/create-checkout-session")
async def create_checkout_session(checkout_request: CheckoutRequest):
    """
    Create Stripe checkout session or return mock URL.
    """
    from .payments import create_checkout_session as stripe_checkout
    
    audit = await get_audit_from_supabase(checkout_request.audit_id)
    
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    
    if audit.get('is_paid'):
        return {
            "already_paid": True,
            "message": "This audit is already unlocked",
            "redirect_url": f"/results/{checkout_request.audit_id}?unlocked=true"
        }
    
    result = await stripe_checkout(
        audit_id=checkout_request.audit_id,
        business_name=audit['business_name'],
        customer_email=str(checkout_request.email) if checkout_request.email else None
    )
    
    return result


@app.post("/api/confirm-payment")
async def confirm_payment(confirm_request: PaymentConfirmRequest):
    """
    audit = await get_audit_from_supabase(confirm_request.audit_id)
    
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    
    if audit.get('is_paid'):
        return {
            "success": True,
            "already_paid": True,
            "message": "Audit already unlocked"
        }
    
    # Check for payment_intent_id (from Stripe Elements)
    if confirm_request.payment_intent_id:
        # Verify with Stripe
        try:
            from .payments import verify_payment_intent
            is_valid = await verify_payment_intent(
                confirm_request.payment_intent_id,
                confirm_request.audit_id
            )
            if is_valid:
                await mark_audit_paid_in_supabase(confirm_request.audit_id)
                return {
                    "success": True,
                    "message": "Full report unlocked",
                    "audit_id": confirm_request.audit_id,
                    "redirect_url": f"/results/{confirm_request.audit_id}?payment=success"
                }
            else:
                raise HTTPException(status_code=400, detail="Payment verification failed")
        except Exception as e:
            # In test mode, allow anyway
            if LOGIC_TEST_MODE:
                await mark_audit_paid_in_supabase(confirm_request.audit_id)
                return {
                    "success": True,
                    "message": "Full report unlocked (test mode)",
                    "audit_id": confirm_request.audit_id
                }
            raise HTTPException(status_code=400, detail=f"Payment verification error: {str(e)}")
    
    # Check for mock/test mode
    is_test = audit.get('audit_payload', {}).get('_metadata', {}).get('isTest', False)
    
    if LOGIC_TEST_MODE or is_test or (confirm_request.session_id and confirm_request.session_id.startswith('mock_')):
        await mark_audit_paid_in_supabase(confirm_request.audit_id)
        return {
            "success": True,
            "message": "Full report unlocked",
            "audit_id": confirm_request.audit_id,
            "redirect_url": f"/results/{confirm_request.audit_id}?unlocked=true"
        }
    
    raise HTTPException(
        status_code=400, 
        detail="Payment verification required."
    )


class PaymentIntentRequest(BaseModel):
    audit_id: str
    product_type: str = "full_report"


@app.post("/api/create-payment-intent")
async def create_payment_intent(request: PaymentIntentRequest):
    """
    Create a Stripe PaymentIntent for embedded checkout.
    Returns client_secret for Stripe Elements.
    """
    from .payments import create_payment_intent as stripe_payment_intent
    
    audit = await get_audit_from_supabase(request.audit_id)
    
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    
    if audit.get('is_paid'):
        return {
            "already_paid": True,
            "message": "This audit is already unlocked",
            "redirect_url": f"/results/{request.audit_id}?unlocked=true"
        }
    
    result = await stripe_payment_intent(
        audit_id=request.audit_id,
        business_name=audit['business_name'],
        product_type=request.product_type
    )
    
    return result


@app.post("/api/stripe-webhook")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.
    Handles: checkout.session.completed, payment_intent.succeeded
    """
    from .payments import verify_webhook_signature, handle_checkout_completed
    
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    
    event = await verify_webhook_signature(payload, signature)
    
    if not event:
        # In test mode, accept mock webhooks
        if LOGIC_TEST_MODE:
            return {"received": True, "mode": "test"}
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    
    event_type = event.get("type", "")
    
    # Handle checkout session completed (redirect flow)
    if event_type == "checkout.session.completed":
        audit_id = await handle_checkout_completed(event)
        if audit_id:
            await mark_audit_paid_in_supabase(audit_id)
            return {"received": True, "audit_id": audit_id, "event": event_type}
    
    # Handle payment intent succeeded (embedded flow)
    elif event_type == "payment_intent.succeeded":
        payment_intent = event.get("data", {}).get("object", {})
        metadata = payment_intent.get("metadata", {})
        audit_id = metadata.get("audit_id")
        if audit_id:
            await mark_audit_paid_in_supabase(audit_id)
            return {"received": True, "audit_id": audit_id, "event": event_type}
    
    return {"received": True, "event": event_type}


@app.get("/api/payment-config")
async def get_payment_config_endpoint(api_key: Optional[str] = None):
    """Get current payment configuration status (admin only)."""
    admin_key = os.getenv("ADMIN_API_KEY")
    
    # Only allow with valid admin key or in debug mode
    if not DEBUG and api_key != admin_key:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from .payments import get_payment_config
    return get_payment_config()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("src.api:app", host="0.0.0.0", port=port, reload=True)
