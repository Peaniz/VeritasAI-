from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.settings import settings
from src.services.analytics_service import AnalyticsService, init_db
from src.routes.analytics_route import router
import structlog

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("analytics_service_starting")
    init_db()

    svc = AnalyticsService()
    from src.worker import KafkaWorker
    worker = KafkaWorker(svc)
    worker.start()

    yield
    worker.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="VeritasAI Analytics Service", version=settings.app_version, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "analytics-service"}

    return app
