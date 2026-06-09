"""
Stripe Billing route for auth-service.

Endpoints:
    GET  /billing/plans        → public: list plans + prices + features
    POST /billing/checkout     → protected: create Stripe Checkout Session
    POST /billing/portal       → protected: create Stripe Customer Portal Session
    POST /billing/webhook      → public: handle Stripe webhook events
    GET  /billing/status       → protected: current subscription status
"""

import json
import datetime
import structlog
from fastapi import APIRouter, HTTPException, Request, Depends, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from src.entities.user import User, UserPlan
from src.services.auth_service import decode_token
from src.settings import settings

log = structlog.get_logger()
router = APIRouter(prefix="/billing", tags=["billing"])
security = HTTPBearer(auto_error=False)

# ── Lazy import stripe (only if configured) ───────────────────────────────────

def _stripe():
    try:
        import stripe
        if not settings.stripe_secret_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Stripe is not configured on this server.",
            )
        stripe.api_key = settings.stripe_secret_key
        return stripe
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe SDK not installed.",
        )


# ── Auth dependency ───────────────────────────────────────────────────────────

def _get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = User.get_or_none(User.id == payload["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ── Plan catalog ──────────────────────────────────────────────────────────────

PLANS = [
    {
        "id":          "free",
        "name":        "Free",
        "price":       0,
        "currency":    "usd",
        "interval":    None,
        "stripe_price": None,
        "daily_limit": settings.free_daily_limit,
        "max_chars":   settings.free_max_chars,
        "features": [
            f"{settings.free_daily_limit} analyses per day",
            f"Up to {settings.free_max_chars:,} characters per analysis",
            "Linguistic feature breakdown",
            "Text explainability highlights",
        ],
    },
    {
        "id":          "pro",
        "name":        "Pro",
        "price":       999,         # cents → $9.99
        "currency":    "usd",
        "interval":    "month",
        "stripe_price": settings.stripe_pro_price_id,
        "daily_limit": settings.pro_daily_limit,
        "max_chars":   settings.pro_max_chars,
        "features": [
            f"{settings.pro_daily_limit} analyses per day",
            f"Up to {settings.pro_max_chars:,} characters per analysis",
            "All Free features",
            "Full analysis history",
            "CSV export",
            "Priority processing",
        ],
    },
    {
        "id":          "enterprise",
        "name":        "Enterprise",
        "price":       4999,        # cents → $49.99
        "currency":    "usd",
        "interval":    "month",
        "stripe_price": settings.stripe_enterprise_price_id,
        "daily_limit": settings.enterprise_daily_limit,
        "max_chars":   settings.enterprise_max_chars,
        "features": [
            "Unlimited analyses",
            f"Up to {settings.enterprise_max_chars:,} characters per analysis",
            "All Pro features",
            "API key access",
            "Dedicated support",
            "SLA guarantee",
        ],
    },
]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/plans", summary="List subscription plans")
def list_plans():
    """Public endpoint: returns all plans with features and pricing."""
    return {"plans": PLANS, "stripe_publishable_key": settings.stripe_publishable_key}


class CheckoutRequest(BaseModel):
    plan: str  # "pro" or "enterprise"
    success_url: str = ""
    cancel_url: str = ""


@router.post("/checkout", summary="Create Stripe Checkout Session")
def create_checkout(body: CheckoutRequest, current_user: User = Depends(_get_current_user)):
    """Create a Stripe Checkout Session and return the URL to redirect to."""
    stripe = _stripe()

    plan = next((p for p in PLANS if p["id"] == body.plan and p["stripe_price"]), None)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {body.plan}")

    success_url = body.success_url or f"{settings.frontend_url}/billing?success=1"
    cancel_url  = body.cancel_url  or f"{settings.frontend_url}/billing?canceled=1"

    # Ensure the user has a Stripe customer record
    customer_id = current_user.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            name=current_user.full_name,
            metadata={"user_id": str(current_user.id)},
        )
        customer_id = customer.id
        current_user.stripe_customer_id = customer_id
        current_user.save()

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": plan["stripe_price"], "quantity": 1}],
        mode="subscription",
        success_url=success_url + "&session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
        metadata={"user_id": str(current_user.id), "plan": body.plan},
    )

    log.info("checkout_session_created", user_id=str(current_user.id), plan=body.plan)
    return {"checkout_url": session.url, "session_id": session.id}


@router.post("/portal", summary="Create Stripe Customer Portal session")
def create_portal(current_user: User = Depends(_get_current_user)):
    """Create a Stripe Customer Portal session for managing subscription."""
    stripe = _stripe()

    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail="No active subscription found. Please subscribe first.",
        )

    session = stripe.billing_portal.Session.create(
        customer=current_user.stripe_customer_id,
        return_url=f"{settings.frontend_url}/billing",
    )
    return {"portal_url": session.url}


@router.get("/status", summary="Get current subscription status")
def subscription_status(current_user: User = Depends(_get_current_user)):
    """Return current plan, quota usage, and subscription details."""
    today = datetime.date.today()

    # Reset daily counter if it's a new day
    if current_user.analyses_reset_date != today:
        current_user.analyses_today = 0
        current_user.analyses_reset_date = today
        current_user.save()

    plan_info = next((p for p in PLANS if p["id"] == current_user.plan), PLANS[0])

    return {
        "plan":               current_user.plan,
        "analyses_today":     current_user.analyses_today,
        "daily_limit":        plan_info["daily_limit"],
        "max_chars":          plan_info["max_chars"],
        "subscription_status": current_user.stripe_subscription_status,
        "stripe_customer_id": current_user.stripe_customer_id,
        "features":           plan_info["features"],
    }


@router.post("/webhook", summary="Handle Stripe webhook events")
async def stripe_webhook(request: Request):
    """
    Stripe sends signed webhook events here.
    Handles:
      - checkout.session.completed → activate subscription
      - customer.subscription.updated → sync plan
      - customer.subscription.deleted → downgrade to free
    """
    stripe = _stripe()
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not settings.stripe_webhook_secret:
        log.warning("stripe_webhook_secret_not_set")
        return JSONResponse({"status": "webhook_secret_not_configured"}, status_code=200)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        log.error("stripe_webhook_invalid_signature")
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    event_type = event["type"]
    data = event["data"]["object"]
    log.info("stripe_webhook_received", event_type=event_type)

    # ── checkout.session.completed ────────────────────────────────────────────
    if event_type == "checkout.session.completed":
        user_id = data.get("metadata", {}).get("user_id")
        plan    = data.get("metadata", {}).get("plan")
        sub_id  = data.get("subscription")

        if user_id and plan:
            user = User.get_or_none(User.id == user_id)
            if user:
                user.plan = plan
                user.stripe_subscription_id = sub_id
                user.stripe_subscription_status = "active"
                user.save()
                log.info("user_plan_activated", user_id=user_id, plan=plan)

    # ── customer.subscription.updated ────────────────────────────────────────
    elif event_type == "customer.subscription.updated":
        customer_id = data.get("customer")
        new_status  = data.get("status")
        # Map Stripe price → plan
        items = data.get("items", {}).get("data", [])
        new_plan = None
        if items:
            price_id = items[0].get("price", {}).get("id")
            if price_id == settings.stripe_pro_price_id:
                new_plan = "pro"
            elif price_id == settings.stripe_enterprise_price_id:
                new_plan = "enterprise"

        user = User.get_or_none(User.stripe_customer_id == customer_id)
        if user:
            if new_plan:
                user.plan = new_plan
            user.stripe_subscription_status = new_status
            user.save()
            log.info("subscription_updated", customer=customer_id, plan=new_plan, status=new_status)

    # ── customer.subscription.deleted ────────────────────────────────────────
    elif event_type == "customer.subscription.deleted":
        customer_id = data.get("customer")
        user = User.get_or_none(User.stripe_customer_id == customer_id)
        if user:
            user.plan = UserPlan.FREE.value
            user.stripe_subscription_id = None
            user.stripe_subscription_status = "canceled"
            user.save()
            log.info("subscription_canceled", customer=customer_id)

    return JSONResponse({"status": "ok"}, status_code=200)
