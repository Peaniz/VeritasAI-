from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.dtos.auth.req import RegisterRequest, LoginRequest, RefreshRequest, UpdateProfileRequest
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
