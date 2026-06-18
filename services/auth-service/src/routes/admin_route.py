import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from src.services.auth_service import decode_token, AuthService
from src.entities.user import User
import structlog

log = structlog.get_logger()
router = APIRouter(prefix="/auth/admin", tags=["admin"])
security = HTTPBearer()
auth_svc = AuthService()


def _require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = auth_svc.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


class UpdatePlanRequest(BaseModel):
    plan: str


@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    _admin=Depends(_require_admin),
):
    q = User.select().order_by(User.created_at.desc())
    if search:
        q = q.where((User.email.contains(search)) | (User.full_name.contains(search)))
    total = q.count()
    offset = (page - 1) * page_size
    users = list(q.offset(offset).limit(page_size))
    return {
        "items": [
            {
                "id": str(u.id),
                "email": u.email,
                "full_name": u.full_name,
                "role": u.role,
                "plan": u.plan,
                "is_verified": u.is_verified,
                "analyses_today": u.analyses_today,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": -(-total // page_size),
    }


@router.put("/users/{user_id}/plan")
def update_user_plan(
    user_id: str,
    body: UpdatePlanRequest,
    _admin=Depends(_require_admin),
):
    if body.plan not in ("free", "pro", "enterprise"):
        raise HTTPException(status_code=400, detail="Invalid plan. Must be free, pro, or enterprise")
    user = User.get_or_none(User.id == user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.plan = body.plan
    user.save()
    log.info("admin_plan_updated", target_user_id=user_id, new_plan=body.plan)
    return {"id": str(user.id), "email": user.email, "plan": user.plan}


@router.get("/stats")
def system_stats(_admin=Depends(_require_admin)):
    today = datetime.date.today()
    return {
        "total_users": User.select().count(),
        "free_users": User.select().where(User.plan == "free").count(),
        "pro_users": User.select().where(User.plan == "pro").count(),
        "enterprise_users": User.select().where(User.plan == "enterprise").count(),
        "admin_users": User.select().where(User.role == "admin").count(),
        "active_today": User.select().where(User.analyses_reset_date == today).count(),
    }
