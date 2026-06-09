"""
VeritasAI Backend – FastAPI application factory.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import detect, models

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Backend starting – pre-loading default model …")
    await detect.preload_default()
    log.info("Backend ready. Default model: %s", settings.default_model)
    yield
    log.info("Backend shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "VeritasAI Backend",
    description = "AI-generated content detection API powering the VeritasAI platform.",
    version     = "1.0.0",
    lifespan    = lifespan,
)

# Allow the Vite dev server (and preview server) to reach the API
app.add_middleware(
    CORSMiddleware,
    allow_origins     = [
        "http://localhost:5173",   # Vite dev
        "http://localhost:4173",   # Vite preview
        "http://127.0.0.1:5173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(detect.router, prefix="/api", tags=["Detection"])
app.include_router(models.router, prefix="/api", tags=["Models"])


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["Health"])
async def health():
    return {
        "status"        : "ok",
        "default_model" : settings.default_model,
        "models_root"   : str(settings.models_root),
    }
