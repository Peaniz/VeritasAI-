from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.settings import settings
from src.services.document_service import DocumentService, init_db
from src.routes.document_route import router as doc_router
import structlog

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("document_service_starting")
    init_db()

    from src.worker import KafkaWorker
    doc_svc = DocumentService()
    worker = KafkaWorker(doc_svc)
    worker.start()

    yield

    log.info("document_service_stopping")
    worker.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="VeritasAI Document Service",
        version=settings.app_version,
        docs_url="/docs",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(doc_router)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "document-service"}

    return app
