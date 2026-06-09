"""
Models router

GET  /api/models              – list all models with full specs
GET  /api/models/{model_name} – single model spec
GET  /api/models/comparison/plot – serve the comparison PNG image
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config  import settings
from app.schemas import ModelSpec, SliceMetric

log = logging.getLogger(__name__)
router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_comparison_results() -> list[dict]:
    """Load comparison_results.json produced by pipeline.py --compare."""
    path = settings.models_root / "comparison_results.json"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def _is_available(model_name: str) -> bool:
    return (settings.models_root / model_name / "config.json").exists()


def _spec_from_dict(d: dict) -> ModelSpec:
    name = d["model_name"]
    return ModelSpec(
        model_name       = name,
        short_name       = name.replace("-base-uncased", ""),
        available        = _is_available(name),
        accuracy         = d.get("accuracy",          0.0),
        precision        = d.get("precision",         0.0),
        recall           = d.get("recall",            0.0),
        f1               = d.get("f1",                0.0),
        auc_roc          = d.get("auc_roc",           0.0),
        tpr_at_fpr01     = d.get("tpr_at_fpr01",      0.0),
        tpr_at_fpr05     = d.get("tpr_at_fpr05",      0.0),
        tpr_at_fpr10     = d.get("tpr_at_fpr10",      0.0),
        test_loss        = d.get("test_loss",         0.0),
        num_parameters   = d.get("num_parameters",    0),
        model_size_mb    = d.get("model_size_mb",     0.0),
        avg_inference_ms = d.get("avg_inference_ms",  0.0),
        threshold        = d.get("threshold",         0.5),
        test_samples     = d.get("test_samples",      0),
        confusion_matrix = d.get("confusion_matrix",  []),
        slice_metrics    = [SliceMetric(**s) for s in d.get("slice_metrics", [])],
    )


def _fallback_specs() -> list[ModelSpec]:
    """Return minimal specs when comparison_results.json does not exist."""
    return [
        ModelSpec(
            model_name    = name,
            short_name    = name.replace("-base-uncased", ""),
            available     = _is_available(name),
        )
        for name in settings.available_models
    ]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/models", response_model=list[ModelSpec], summary="List all available models with specs")
async def list_models() -> list[ModelSpec]:
    data = _load_comparison_results()
    if data:
        return [_spec_from_dict(d) for d in data]
    return _fallback_specs()


@router.get("/models/comparison/plot", summary="Return the model comparison PNG plot")
async def comparison_plot():
    # Look in plot/ directory (sibling of models/)
    plot_dir  = settings.models_root.parent / "plot"
    plot_path = plot_dir / "model_comparison.png"
    if not plot_path.exists():
        raise HTTPException(status_code=404, detail="Comparison plot not found. Run: uv run python pipeline.py --compare")
    return FileResponse(str(plot_path), media_type="image/png")


@router.get("/models/{model_name}", response_model=ModelSpec, summary="Get spec for a single model")
async def get_model(model_name: str) -> ModelSpec:
    if model_name not in settings.available_models:
        raise HTTPException(status_code=400, detail=f"Unknown model: {model_name}")

    data = _load_comparison_results()
    for d in data:
        if d["model_name"] == model_name:
            return _spec_from_dict(d)

    # Return minimal spec if not in comparison results
    return ModelSpec(
        model_name = model_name,
        short_name = model_name.replace("-base-uncased", ""),
        available  = _is_available(model_name),
    )
