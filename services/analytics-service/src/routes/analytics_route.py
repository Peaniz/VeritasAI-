import jwt as pyjwt
from fastapi import APIRouter, Query, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.services.analytics_service import AnalyticsService
from src.settings import settings

router = APIRouter(prefix="/analytics", tags=["analytics"])
svc = AnalyticsService()
_security = HTTPBearer()


def _require_admin(credentials: HTTPAuthorizationCredentials = Depends(_security)):
    try:
        payload = pyjwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    if payload.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return payload


@router.get("/dashboard")
def dashboard(user_id: str = Query(...)):
    return svc.get_dashboard_stats(user_id)


@router.get("/admin/overview")
def admin_overview(_admin=Depends(_require_admin)):
    return svc.get_system_overview()


@router.get("/health")
def health():
    return {"status": "ok", "service": "analytics-service"}
