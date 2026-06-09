"""
Google OAuth 2.0 route for auth-service.
Endpoints:
    GET /auth/google           → redirect user to Google consent screen
    GET /auth/google/callback  → exchange code, upsert user, issue JWT
"""

import secrets
from datetime import datetime, timedelta

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from src.entities.user import GoogleOAuthState, User
from src.services.auth_service import create_access_token, create_refresh_token, hash_token
from src.settings import settings
from src.entities.user import RefreshToken

log = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["google-oauth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _clean_expired_states():
    """Remove old/used OAuth state tokens (housekeeping)."""
    GoogleOAuthState.delete().where(
        (GoogleOAuthState.expires_at < datetime.utcnow()) |
        (GoogleOAuthState.used == True)
    ).execute()


@router.get("/google", summary="Initiate Google OAuth flow")
def google_login():
    """Generate a CSRF state token and redirect to Google's OAuth screen."""
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured on this server.",
        )

    state = secrets.token_urlsafe(32)
    GoogleOAuthState.create(
        state=state,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    _clean_expired_states()

    params = {
        "client_id":     settings.google_client_id,
        "redirect_uri":  settings.google_redirect_uri,
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         state,
        "access_type":   "offline",
        "prompt":        "select_account",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{query}")


@router.get("/google/callback", summary="Google OAuth callback")
def google_callback(
    code:  str = Query(...),
    state: str = Query(...),
    error: str | None = Query(None),
):
    """Exchange auth code for tokens, upsert user, issue JWT and redirect to frontend."""

    if error:
        log.warning("google_oauth_error", error=error)
        return RedirectResponse(
            url=f"{settings.frontend_url}/login?error=google_auth_denied"
        )

    # ── Validate CSRF state ───────────────────────────────────────────────────
    state_record = GoogleOAuthState.get_or_none(
        GoogleOAuthState.state == state,
        GoogleOAuthState.used == False,
        GoogleOAuthState.expires_at > datetime.utcnow(),
    )
    if not state_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state. Please try logging in again.",
        )

    state_record.used = True
    state_record.save()

    # ── Exchange code for Google tokens ───────────────────────────────────────
    with httpx.Client(timeout=10) as client:
        token_resp = client.post(GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri":  settings.google_redirect_uri,
            "grant_type":    "authorization_code",
        })

    if token_resp.status_code != 200:
        log.error("google_token_exchange_failed", body=token_resp.text)
        return RedirectResponse(
            url=f"{settings.frontend_url}/login?error=google_token_failed"
        )

    token_data = token_resp.json()
    access_token_google = token_data.get("access_token")

    # ── Fetch user info from Google ───────────────────────────────────────────
    with httpx.Client(timeout=10) as client:
        userinfo_resp = client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token_google}"},
        )

    if userinfo_resp.status_code != 200:
        log.error("google_userinfo_failed", body=userinfo_resp.text)
        return RedirectResponse(
            url=f"{settings.frontend_url}/login?error=google_userinfo_failed"
        )

    info = userinfo_resp.json()
    google_id  = info.get("sub")
    email      = info.get("email")
    name       = info.get("name") or email.split("@")[0]
    avatar_url = info.get("picture")
    verified   = info.get("email_verified", False)

    if not google_id or not email:
        return RedirectResponse(
            url=f"{settings.frontend_url}/login?error=google_missing_email"
        )

    # ── Upsert user ───────────────────────────────────────────────────────────
    user = User.get_or_none(User.google_id == google_id)
    if not user:
        # Try to link by email (existing email/password account)
        user = User.get_or_none(User.email == email)

    if user:
        # Update Google info on every login
        user.google_id  = google_id
        user.avatar_url = avatar_url
        user.is_verified = verified
        if not user.full_name:
            user.full_name = name
        user.save()
    else:
        # New user via Google
        user = User.create(
            email=email,
            full_name=name,
            avatar_url=avatar_url,
            google_id=google_id,
            is_verified=verified,
        )

    log.info("google_login_success", user_id=str(user.id), email=email)

    # ── Issue JWT ─────────────────────────────────────────────────────────────
    jwt_access  = create_access_token(str(user.id), user.email, user.role, user.plan)
    jwt_refresh = create_refresh_token(str(user.id))

    RefreshToken.create(
        user=user,
        token_hash=hash_token(jwt_refresh),
        expires_at=datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days),
    )

    # ── Redirect to frontend with tokens in URL fragment ──────────────────────
    # The frontend reads these from the URL hash and stores in localStorage.
    return RedirectResponse(
        url=(
            f"{settings.frontend_url}/auth/callback"
            f"#access_token={jwt_access}"
            f"&refresh_token={jwt_refresh}"
            f"&plan={user.plan}"
        )
    )
