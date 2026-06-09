"""
Detect router – POST /api/detect

Supports model selection via the `model` field in the request body.
Detectors are loaded lazily and cached after first use.
"""
from __future__ import annotations

import sys
import logging
from fastapi import APIRouter, HTTPException

from app.config  import settings
from app.schemas import DetectRequest, DetectResponse

log = logging.getLogger(__name__)

# ── Lazy detector cache ───────────────────────────────────────────────────────
_detectors: dict[str, object] = {}


def _get_detector(model_name: str):
    """Return a cached AIContentDetector, loading it on first call."""
    if model_name in _detectors:
        return _detectors[model_name]

    model_dir = settings.models_root / model_name
    if not (model_dir / "config.json").exists():
        raise HTTPException(
            status_code=503,
            detail=f"Model '{model_name}' is not available. "
                   f"Expected directory: {model_dir}",
        )

    # Add .../AI-Generated-Content-Detection-System/src/ to sys.path so we can
    # import inference.detector without copying code.
    src_path = str(settings.src_root)  # ends with /src
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from inference.detector import AIContentDetector  # type: ignore
    log.info("Loading detector for %s …", model_name)
    _detectors[model_name] = AIContentDetector(str(model_dir))
    log.info("Detector ready: %s", model_name)
    return _detectors[model_name]


async def preload_default() -> None:
    """Called at startup to warm-up the default model."""
    try:
        _get_detector(settings.default_model)
    except Exception as exc:
        log.warning("Could not pre-load default model: %s", exc)


# ── Router ────────────────────────────────────────────────────────────────────
router = APIRouter()


@router.post("/detect", response_model=DetectResponse, summary="Detect AI-generated content")
async def detect_text(req: DetectRequest) -> DetectResponse:
    """
    Analyse `text` and return AI vs Human classification.

    - **text**: The text to analyse (1 – 50 000 characters)
    - **model**: `distilbert-base-uncased` (default, faster) or `bert-base-uncased`
    """
    model_name = req.model
    if model_name not in settings.available_models:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model '{model_name}'. "
                   f"Choose from: {settings.available_models}",
        )

    detector = _get_detector(model_name)
    result   = detector.predict(req.text)  # returns a dict or Pydantic model

    # Normalize label to match frontend expectations: "ai" -> "AI", "human" -> "Human"
    if isinstance(result, dict) and "label" in result:
        lbl = result["label"]
        result["label"] = "AI" if lbl.lower() == "ai" else "Human"

    return result
