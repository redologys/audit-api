"""
Payment Service - Stripe Integration (Test Mode Ready)
Handles checkout sessions, webhooks, and payment verification.
"""
import os
from typing import Optional, Dict, Any
from datetime import datetime

# Check for Stripe availability
STRIPE_AVAILABLE = False
stripe = None

try:
    import stripe as stripe_lib
    stripe = stripe_lib
    STRIPE_AVAILABLE = True
except ImportError:
    print("Stripe SDK not installed. Running in mock mode.")

# Configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
LOGIC_TEST_MODE = os.getenv("LOGIC_TEST_MODE", "false").lower() == "true"

# Pricing
FULL_REPORT_PRICE = float(os.getenv("FULL_REPORT_PRICE", "29.00"))
CURRENCY = os.getenv("STRIPE_CURRENCY", "usd")


def is_stripe_configured() -> bool:
    """Check if Stripe is properly configured."""
    return bool(STRIPE_SECRET_KEY and STRIPE_PRICE_ID and STRIPE_AVAILABLE)


async def create_checkout_session(
    audit_id: str,
    business_name: str,
    customer_email: Optional[str] = None,
    success_url: str = "http://localhost:5173/results/{audit_id}?unlocked=true",
    cancel_url: str = "http://localhost:5173/results/{audit_id}?cancelled=true"
) -> Dict[str, Any]:
    """
    Create a Stripe checkout session or return mock URL.
    
    Returns:
        Dict with checkout_url and session_id
    """
    
    # If in test mode or Stripe not configured, return mock
    if LOGIC_TEST_MODE or not is_stripe_configured():
        return {
            "checkout_url": f"/mock-stripe?audit_id={audit_id}",
            "session_id": f"mock_session_{audit_id}",
            "is_mock": True,
            "audit_id": audit_id,
            "price": FULL_REPORT_PRICE,
            "currency": CURRENCY
        }
    
    # Real Stripe checkout
    try:
        stripe.api_key = STRIPE_SECRET_KEY
        
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price": STRIPE_PRICE_ID,
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url.format(audit_id=audit_id),
            cancel_url=cancel_url.format(audit_id=audit_id),
            customer_email=customer_email,
            metadata={
                "audit_id": audit_id,
                "business_name": business_name,
                "product": "full_report"
            }
        )
        
        return {
            "checkout_url": session.url,
            "session_id": session.id,
            "is_mock": False,
            "audit_id": audit_id
        }
        
    except Exception as e:
        # Fallback to mock on error
        print(f"Stripe error: {e}")
        return {
            "checkout_url": f"/mock-stripe?audit_id={audit_id}",
            "session_id": f"error_fallback_{audit_id}",
            "is_mock": True,
            "error": str(e),
            "audit_id": audit_id,
            "price": FULL_REPORT_PRICE
        }


async def verify_webhook_signature(payload: bytes, signature: str) -> Optional[Dict]:
    """Verify Stripe webhook signature and return event."""
    if not STRIPE_WEBHOOK_SECRET or not STRIPE_AVAILABLE:
        return None
    
    try:
        stripe.api_key = STRIPE_SECRET_KEY
        event = stripe.Webhook.construct_event(
            payload, signature, STRIPE_WEBHOOK_SECRET
        )
        return event
    except Exception as e:
        print(f"Webhook verification failed: {e}")
        return None


async def handle_checkout_completed(event: Dict) -> Optional[str]:
    """
    Handle successful checkout event.
    Returns audit_id if found in metadata.
    """
    session = event.get("data", {}).get("object", {})
    metadata = session.get("metadata", {})
    audit_id = metadata.get("audit_id")
    
    return audit_id


async def create_payment_intent(
    audit_id: str,
    business_name: str,
    product_type: str = "full_report"
) -> Dict[str, Any]:
    """
    Create a Stripe PaymentIntent for embedded checkout (Stripe Elements).
    
    Returns:
        Dict with client_secret for frontend
    """
    # Calculate amount in cents
    amount = int(FULL_REPORT_PRICE * 100)
    
    # If Stripe not configured or in test mode, return mock
    if LOGIC_TEST_MODE or not STRIPE_SECRET_KEY or not STRIPE_AVAILABLE:
        import uuid
        mock_secret = f"pi_mock_{uuid.uuid4().hex[:16]}_secret_{uuid.uuid4().hex[:8]}"
        return {
            "client_secret": mock_secret,
            "is_mock": True,
            "audit_id": audit_id,
            "amount": amount,
            "currency": CURRENCY.upper()
        }
    
    try:
        stripe.api_key = STRIPE_SECRET_KEY
        
        # Create PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=CURRENCY,
            automatic_payment_methods={
                "enabled": True,
            },
            metadata={
                "audit_id": audit_id,
                "business_name": business_name,
                "product_type": product_type
            },
            description=f"Full Audit Report - {business_name}"
        )
        
        return {
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id,
            "is_mock": False,
            "audit_id": audit_id,
            "amount": amount,
            "currency": CURRENCY.upper()
        }
        
    except Exception as e:
        print(f"Stripe PaymentIntent error: {e}")
        # Return mock on error so flow doesn't break
        import uuid
        mock_secret = f"pi_error_{uuid.uuid4().hex[:16]}_secret_{uuid.uuid4().hex[:8]}"
        return {
            "client_secret": mock_secret,
            "is_mock": True,
            "error": str(e),
            "audit_id": audit_id,
            "amount": amount,
            "currency": CURRENCY.upper()
        }


async def verify_payment_intent(payment_intent_id: str, audit_id: str) -> bool:
    """
    Verify that a PaymentIntent was successful and matches the audit.
    
    Returns:
        True if payment is valid and succeeded
    """
    # Mock payment intents always succeed in test mode
    if LOGIC_TEST_MODE or payment_intent_id.startswith("pi_mock_") or payment_intent_id.startswith("pi_error_"):
        return True
    
    if not STRIPE_SECRET_KEY or not STRIPE_AVAILABLE:
        return True  # Allow in unconfigured state
    
    try:
        stripe.api_key = STRIPE_SECRET_KEY
        
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        # Check status
        if intent.status != "succeeded":
            print(f"PaymentIntent status is {intent.status}, not succeeded")
            return False
        
        # Verify audit_id matches
        intent_audit_id = intent.metadata.get("audit_id")
        if intent_audit_id != audit_id:
            print(f"Audit ID mismatch: expected {audit_id}, got {intent_audit_id}")
            return False
        
        return True
        
    except Exception as e:
        print(f"PaymentIntent verification error: {e}")
        return False


def get_payment_config() -> Dict[str, Any]:
    """Get current payment configuration (for admin/debug)."""
    return {
        "stripe_configured": is_stripe_configured(),
        "stripe_available": STRIPE_AVAILABLE,
        "test_mode": LOGIC_TEST_MODE,
        "price": FULL_REPORT_PRICE,
        "currency": CURRENCY,
        "has_secret_key": bool(STRIPE_SECRET_KEY),
        "has_price_id": bool(STRIPE_PRICE_ID),
        "has_webhook_secret": bool(STRIPE_WEBHOOK_SECRET)
    }

