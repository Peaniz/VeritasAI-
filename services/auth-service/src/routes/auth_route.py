import datetime
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from src.dtos.auth.req import RegisterRequest, LoginRequest, RefreshRequest, UpdateProfileRequest, UpdatePreferencesRequest
from src.dtos.auth.res import RegisterResponse, LoginResponse, RefreshResponse, UserOut, TokenPair
from src.services.auth_service import AuthService, decode_token
from src.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])
auth_svc = AuthService()
security = HTTPBearer()


def _user_out(user) -> UserOut:
    return UserOut(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        role=user.role,
        plan=user.plan,
        is_verified=user.is_verified,
        has_google=bool(user.google_id),
        analyses_today=user.analyses_today,
        created_at=user.created_at.isoformat(),
        preferences=user.preferences,
    )


def _get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """FastAPI dependency: validate Bearer token and return user."""
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = auth_svc.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest):
    try:
        user, access_token, refresh_token = auth_svc.register(
            body.email, body.password, body.full_name
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return RegisterResponse(
        user=_user_out(user),
        tokens=TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        ),
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    try:
        user, access_token, refresh_token = auth_svc.login(body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    return LoginResponse(
        user=_user_out(user),
        tokens=TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        ),
    )


@router.post("/refresh", response_model=RefreshResponse)
def refresh(body: RefreshRequest):
    try:
        access_token, refresh_token = auth_svc.refresh(body.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    return RefreshResponse(
        tokens=TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )
    )


@router.get("/me", response_model=UserOut)
def me(current_user=Depends(_get_current_user)):
    """Return current authenticated user."""
    return _user_out(current_user)


@router.put("/me", response_model=UserOut)
def update_me(body: UpdateProfileRequest, current_user=Depends(_get_current_user)):
    """Update profile fields (name) for current user."""
    updated = auth_svc.update_profile(current_user, full_name=body.full_name)
    return _user_out(updated)


@router.put("/preferences", response_model=UserOut)
def update_preferences(body: UpdatePreferencesRequest, current_user=Depends(_get_current_user)):
    """Update preferences JSON string for current user."""
    current_user.preferences = body.preferences
    current_user.save()
    return _user_out(current_user)


# ── Internal: quota check + increment (called by document-service) ────────────

class QuotaConsumeRequest(BaseModel):
    user_id: str
    char_count: int


@router.post("/internal/quota-consume")
def quota_consume(body: QuotaConsumeRequest):
    """Atomically check and increment daily scan quota. Returns 429 or 400 on violation."""
    from src.entities.user import User
    user = auth_svc.get_user_by_id(body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    today = datetime.date.today()
    if user.analyses_reset_date != today:
        user.analyses_today = 0
        user.analyses_reset_date = today

    plan = user.plan
    if plan == "pro":
        daily_limit, max_chars = settings.pro_daily_limit, settings.pro_max_chars
    elif plan == "enterprise":
        daily_limit, max_chars = 0, settings.enterprise_max_chars  # 0 = unlimited
    else:
        daily_limit, max_chars = settings.free_daily_limit, settings.free_max_chars

    if body.char_count > max_chars:
        raise HTTPException(
            status_code=400,
            detail=f"Text exceeds {max_chars:,} character limit for {plan} plan",
        )
    if daily_limit and user.analyses_today >= daily_limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily quota of {daily_limit} scans exceeded for {plan} plan",
        )

    user.analyses_today += 1
    user.save()
    return {"analyses_today": user.analyses_today, "plan": plan}

