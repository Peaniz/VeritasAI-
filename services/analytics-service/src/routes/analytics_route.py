from fastapi import APIRouter, Query
from src.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])
svc = AnalyticsService()


@router.get("/dashboard")
def dashboard(user_id: str = Query(...)):
    return svc.get_dashboard_stats(user_id)


@router.get("/health")
def health():
    return {"status": "ok", "service": "analytics-service"}
