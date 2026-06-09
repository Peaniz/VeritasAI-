import json
import math
from fastapi import APIRouter, HTTPException, Header, status, Query
from src.dtos.document.req import CreateDocumentRequest
from src.dtos.document.res import DocumentOut, DocumentDetailOut, PaginatedDocuments, AnalysisResultOut
from src.services.document_service import DocumentService
from src.lib.event_bus.kafka.producer import get_producer
import structlog

log = structlog.get_logger()
router = APIRouter(prefix="/documents", tags=["documents"])
doc_svc = DocumentService()


def _doc_out(doc) -> DocumentOut:
    return DocumentOut(
        id=str(doc.id),
        user_id=str(doc.user_id),
        title=doc.title,
        file_type=doc.file_type,
        char_count=doc.char_count,
        word_count=doc.word_count,
        status=doc.status,
        created_at=doc.created_at.isoformat(),
    )


def _analysis_out(ar) -> AnalysisResultOut:
    return AnalysisResultOut(
        id=str(ar.id),
        document_id=str(ar.document_id),
        model_name=ar.model_name,
        label=ar.label,
        ai_score=ar.ai_score,
        human_score=ar.human_score,
        confidence=ar.confidence,
        threshold=ar.threshold,
        highlight_spans=json.loads(ar.highlight_spans),
        linguistic_features=json.loads(ar.linguistic_features),
        explanations=json.loads(ar.explanations),
        inference_ms=ar.inference_ms,
        created_at=ar.created_at.isoformat(),
    )


@router.post("/", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(body: CreateDocumentRequest):
    doc = doc_svc.create_document(
        user_id=body.user_id,
        title=body.title,
        content=body.content,
        file_type=body.file_type,
    )
    # Publish to Kafka so ai-service picks it up
    producer = get_producer()
    producer.publish(
        topic="document.created",
        key=str(doc.id),
        value={
            "document_id": str(doc.id),
            "user_id": str(doc.user_id),
            "content": body.content,
            "title": body.title,
        },
    )
    return _doc_out(doc)


@router.get("/", response_model=PaginatedDocuments)
def list_documents(
    user_id: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    docs, total = doc_svc.list_documents(user_id, page, page_size)
    return PaginatedDocuments(
        items=[_doc_out(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/{doc_id}", response_model=DocumentDetailOut)
def get_document(doc_id: str, user_id: str = Query(...)):
    doc = doc_svc.get_document(doc_id, user_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    ar = doc_svc.get_analysis_result(doc_id)
    return DocumentDetailOut(
        document=_doc_out(doc),
        analysis=_analysis_out(ar) if ar else None,
    )
