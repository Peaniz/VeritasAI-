"""
Frontend-compatible API routes.
Maps the paths the React frontend expects to the underlying pipeline.
  POST /api/detect   — AI detection (frontend sends {text, model})
  GET  /api/models   — Full model specs including comparison stats
  POST /api/translate — Translation proxy using deep-translator
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from src.services.detection_pipeline import AIDetectionPipeline
from src.settings import settings
import structlog
import asyncio

log = structlog.get_logger()
api_router = APIRouter(prefix="/api", tags=["api"])

_pipeline: AIDetectionPipeline | None = None


def get_pipeline() -> AIDetectionPipeline:
    if _pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models not loaded yet",
        )
    return _pipeline


def set_api_pipeline(pipeline: AIDetectionPipeline) -> None:
    global _pipeline
    _pipeline = pipeline


# ── Detect ────────────────────────────────────────────────────────────────────

class DetectRequest(BaseModel):
    text: str
    model: str | None = None


@api_router.post("/detect")
def api_detect(body: DetectRequest, pipeline: AIDetectionPipeline = Depends(get_pipeline)):
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Text cannot be empty")
    if len(text) > settings.max_text_length:
        raise HTTPException(status_code=422, detail=f"Text too long (max {settings.max_text_length} chars)")
    try:
        result = pipeline.analyze(text, body.model)
    except Exception as exc:
        log.error("api_detect_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    # Normalize label to 'AI'/'Human' as expected by frontend
    result["label"] = "AI" if str(result.get("label", "")).lower() == "ai" else "Human"
    return result


# ── Models ────────────────────────────────────────────────────────────────────

@api_router.get("/models")
def api_models(pipeline: AIDetectionPipeline = Depends(get_pipeline)):
    return pipeline.available_models_full()


# ── Translate ─────────────────────────────────────────────────────────────────

class TranslateRequest(BaseModel):
    text: str
    source_lang: str = "en"
    target_lang: str = "vi"


def _do_translate(text: str, source: str, target: str) -> tuple[str, float]:
    """Translate text using deep-translator (Google Translate backend)."""
    try:
        from deep_translator import GoogleTranslator
        # deep-translator uses language names or codes; handle zh variants
        src = "zh-CN" if source in ("zh", "zh-cn") else "zh-TW" if source == "zh-TW" else source
        tgt = "zh-CN" if target in ("zh", "zh-cn") else "zh-TW" if target == "zh-TW" else target
        translator = GoogleTranslator(source=src, target=tgt)
        # Split long text into chunks of 4500 chars to stay within limits
        if len(text) <= 4500:
            translated = translator.translate(text)
        else:
            chunks = [text[i:i + 4500] for i in range(0, len(text), 4500)]
            translated = " ".join(translator.translate(chunk) for chunk in chunks if chunk.strip())
        return translated or text, 0.95
    except ImportError:
        # Fallback to MyMemory if deep-translator not installed
        raise RuntimeError("deep-translator not installed; run: uv add deep-translator")
    except Exception as exc:
        raise RuntimeError(f"Translation failed: {exc}")


@api_router.post("/translate")
async def api_translate(body: TranslateRequest):
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty")
    if len(body.text) > 10000:
        raise HTTPException(status_code=422, detail="Text too long (max 10000 chars)")
    try:
        loop = asyncio.get_event_loop()
        translated, quality = await loop.run_in_executor(
            None, _do_translate, body.text, body.source_lang, body.target_lang
        )
        return {"translated_text": translated, "quality": quality}
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
