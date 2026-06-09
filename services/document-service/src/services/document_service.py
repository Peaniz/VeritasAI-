import json
import urllib.parse
import peewee as pw
from minio import Minio
from minio.error import S3Error
from src.settings import settings
from src.entities.document import Document, AnalysisResult, database_proxy
import structlog

log = structlog.get_logger()


def init_db():
    parsed = urllib.parse.urlparse(settings.database_url)
    db = pw.PostgresqlDatabase(
        parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname,
        port=parsed.port or 5432,
    )
    database_proxy.initialize(db)
    db.connect(reuse_if_open=True)
    db.create_tables([Document, AnalysisResult], safe=True)
    log.info("document_db_initialized")
    return db


def get_minio() -> Minio:
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=settings.minio_secure,
    )
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)
    return client


class DocumentService:
    def __init__(self):
        self._minio = get_minio()

    def create_document(self, user_id: str, title: str, content: str, file_type: str = "text") -> Document:
        words = content.split()
        doc = Document.create(
            user_id=user_id,
            title=title,
            content=content,
            file_type=file_type,
            char_count=len(content),
            word_count=len(words),
            status="pending",
        )
        log.info("document_created", doc_id=str(doc.id))
        return doc

    def get_document(self, doc_id: str, user_id: str | None = None) -> Document | None:
        q = Document.select().where(Document.id == doc_id)
        if user_id:
            q = q.where(Document.user_id == user_id)
        return q.first()

    def list_documents(self, user_id: str, page: int = 1, page_size: int = 20):
        offset = (page - 1) * page_size
        total = Document.select().where(Document.user_id == user_id).count()
        docs = (
            Document.select()
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(docs), total

    def save_analysis_result(self, document_id: str, result: dict) -> AnalysisResult:
        doc = Document.get_by_id(document_id)
        doc.status = "done"
        doc.save()

        ar = AnalysisResult.create(
            document=doc,
            model_name=result.get("model_name", "unknown"),
            label=result.get("label", "unknown"),
            ai_score=result.get("ai_probability", 0.0),
            human_score=result.get("human_probability", 0.0),
            confidence=result.get("confidence", 0.0),
            threshold=result.get("threshold", 0.5),
            highlight_spans=json.dumps(result.get("highlight_spans", [])),
            linguistic_features=json.dumps(result.get("linguistic_features", {})),
            explanations=json.dumps(result.get("explanations", [])),
            inference_ms=result.get("inference_time_ms", 0.0),
        )
        log.info("analysis_result_saved", doc_id=document_id, label=result.get("label"))
        return ar

    def get_analysis_result(self, document_id: str) -> AnalysisResult | None:
        return (
            AnalysisResult.select()
            .where(AnalysisResult.document == document_id)
            .order_by(AnalysisResult.created_at.desc())
            .first()
        )
