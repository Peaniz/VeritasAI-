from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.settings import settings
from src.services.detection_pipeline import AIDetectionPipeline
from src.routes.detection_route import router as detection_router, set_pipeline
from src.routes.api_route import api_router, set_api_pipeline
import structlog

log = structlog.get_logger()
_pipeline: AIDetectionPipeline | None = None
_kafka_worker = None
_grpc_server = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pipeline, _kafka_worker, _grpc_server

    log.info("ai_service_starting", models_dir=settings.models_dir)
    _pipeline = AIDetectionPipeline(
        models_dir=settings.models_dir,
        default_model=settings.default_model,
        max_length=256,
    )
    _pipeline.load_models()
    set_pipeline(_pipeline)
    set_api_pipeline(_pipeline)

    # Kafka consumer
    from src.worker import KafkaWorker
    _kafka_worker = KafkaWorker(_pipeline)
    _kafka_worker.start()

    # gRPC server
    from src.grpc.detection_servicer import serve_grpc
    _grpc_server = serve_grpc(_pipeline)

    log.info("ai_service_ready", available_models=[m["name"] for m in _pipeline.available_models()])
    yield

    log.info("ai_service_stopping")
    if _kafka_worker:
        _kafka_worker.stop()
    if _grpc_server:
        _grpc_server.stop(grace=5)


def create_app() -> FastAPI:
    app = FastAPI(
        title="VeritasAI AI Detection Service",
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

    app.include_router(detection_router)
    app.include_router(api_router)

    @app.get("/health")
    def health():
        loaded = _pipeline is not None and bool(_pipeline.available_models() if _pipeline else [])
        return {"status": "ok" if loaded else "loading", "service": "ai-service"}

    return app
