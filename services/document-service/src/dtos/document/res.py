import json
from pydantic import BaseModel
from typing import Any


class DocumentOut(BaseModel):
    id: str
    user_id: str
    title: str
    file_type: str
    char_count: int
    word_count: int
    status: str
    created_at: str


class AnalysisResultOut(BaseModel):
    id: str
    document_id: str
    model_name: str
    label: str
    ai_score: float
    human_score: float
    confidence: float
    threshold: float
    highlight_spans: list[Any]
    linguistic_features: dict[str, Any]
    explanations: list[str]
    inference_ms: float
    created_at: str


class DocumentDetailOut(BaseModel):
    document: DocumentOut
    analysis: AnalysisResultOut | None = None


class PaginatedDocuments(BaseModel):
    items: list[DocumentOut]
    total: int
    page: int
    page_size: int
    total_pages: int
