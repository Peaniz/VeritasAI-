from fastapi import APIRouter, HTTPException, Depends, status
from src.dtos.detection.req import AnalyzeRequest, AnalyzeBatchRequest
from src.dtos.detection.res import AnalyzeResponse, ModelsResponse, ModelInfo
from src.services.detection_pipeline import AIDetectionPipeline
from src.settings import settings
import structlog

log = structlog.get_logger()
router = APIRouter(prefix="/detection", tags=["detection"])

_pipeline: AIDetectionPipeline | None = None


def get_pipeline() -> AIDetectionPipeline:
    if _pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models not loaded yet",
        )
    return _pipeline


def set_pipeline(pipeline: AIDetectionPipeline) -> None:
    global _pipeline
    _pipeline = pipeline


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(body: AnalyzeRequest, pipeline: AIDetectionPipeline = Depends(get_pipeline)):
    if len(body.text.strip()) == 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Text cannot be empty")
    if len(body.text) > settings.max_text_length:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Text exceeds max length of {settings.max_text_length} characters",
        )
    try:
        result = pipeline.analyze(body.text, body.model_name)
    except Exception as exc:
        log.error("analyze_failed", error=str(exc))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return AnalyzeResponse(**result)


@router.post("/analyze/batch", response_model=list[AnalyzeResponse])
def analyze_batch(body: AnalyzeBatchRequest, pipeline: AIDetectionPipeline = Depends(get_pipeline)):
    if not body.texts:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Texts list is empty")
    if len(body.texts) > 50:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Batch size too large (max 50)")
    results = pipeline.analyze_batch(body.texts, body.model_name)
    return [AnalyzeResponse(**r) for r in results]


@router.get("/models", response_model=ModelsResponse)
def list_models(pipeline: AIDetectionPipeline = Depends(get_pipeline)):
    models = pipeline.available_models()
    return ModelsResponse(
        models=[ModelInfo(**m) for m in models],
        default_model=settings.default_model,
    )


@router.get("/health")
def health():
    loaded = _pipeline is not None and bool(_pipeline.available_models())
    return {"status": "ok" if loaded else "loading", "models_loaded": loaded}
