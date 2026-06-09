from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.settings import settings
from src.lib.db.peewee import init_db
from src.routes.auth_route import router as auth_router
from src.routes.google_oauth_route import router as google_oauth_router
from src.routes.billing_route import router as billing_router
import structlog

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("auth_service_starting", version=settings.app_version)
    init_db()

    # Start gRPC server in background thread
    import threading
    from src.grpc.auth_servicer import serve_grpc
    grpc_server = serve_grpc()
    if grpc_server:
        log.info("grpc_server_started", port=settings.grpc_port)

    yield

    log.info("auth_service_stopping")
    if grpc_server:
        grpc_server.stop(grace=5)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Veritas Auth Service",
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(google_oauth_router)   # /auth/google, /auth/google/callback
    app.include_router(billing_router)        # /billing/*

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "veritas-auth"}

    return app
