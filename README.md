# VeritasAI Backend

FastAPI backend serving the **AI content detection API** for `main_app`.

## Structure

```
backend/
├── run.py               ← entry point
├── pyproject.toml       ← dependencies (uv)
├── .env                 ← optional overrides (copy from .env.example)
└── app/
    ├── main.py          ← FastAPI app + CORS + lifespan
    ├── config.py        ← path/settings config
    ├── schemas.py       ← Pydantic request / response models
    └── routers/
        ├── detect.py    ← POST /api/detect
        └── models.py    ← GET  /api/models
```

## Quick start

```bash
# 1. Install deps (from backend/)
cd "AI Content Intelligence Platform/backend"
uv sync

# 2. Run
uv run python run.py
# → http://localhost:8000
# → Docs: http://localhost:8000/docs
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/detect` | Detect AI content – pass `text` + optional `model` |
| `GET`  | `/api/models` | List all models with full performance specs |
| `GET`  | `/api/models/{name}` | Single model spec |
| `GET`  | `/api/models/comparison/plot` | PNG comparison chart |
| `GET`  | `/api/health` | Health check |

## Model selection

The `/api/detect` endpoint accepts a `model` field:

```json
{
  "text": "Your text here…",
  "model": "distilbert-base-uncased"
}
```

Available values: `distilbert-base-uncased` | `bert-base-uncased`

## Environment variables (optional `.env`)

```
HOST=0.0.0.0
PORT=8000
RELOAD=false
DEFAULT_MODEL=distilbert-base-uncased
```

## Requirements

Models must be trained first:
```bash
# From AI-Generated-Content-Detection-System/
uv run python pipeline.py --train-both
```
