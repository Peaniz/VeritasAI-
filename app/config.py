from pathlib import Path
from pydantic_settings import BaseSettings

# ── Resolve paths ─────────────────────────────────────────────────────────────
# backend/ is at: AI Content Intelligence Platform/backend/
# AI-Generated-Content-Detection-System/ is a sibling of "AI Content Intelligence Platform/"
_BACKEND_DIR  = Path(__file__).resolve().parent.parent          # …/AI Content Intelligence Platform/backend
_PLATFORM_DIR = _BACKEND_DIR.parent                             # …/AI Content Intelligence Platform/
_REPO_ROOT    = _PLATFORM_DIR.parent                            # …/AI-Generated-Content-Detection-System (workspace root)
_AIDET_DIR    = _REPO_ROOT / "AI-Generated-Content-Detection-System"


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False

    # ── Paths ─────────────────────────────────────────────────────────────────
    models_root: Path = _AIDET_DIR / "models"
    src_root:    Path = _AIDET_DIR / "src"   # contains inference/detector.py

    # ── Model ─────────────────────────────────────────────────────────────────
    default_model: str = "distilbert-base-uncased"
    available_models: list[str] = [
        "distilbert-base-uncased",
        "bert-base-uncased",
    ]


settings = Settings()
