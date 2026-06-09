import uuid
from datetime import datetime
import peewee as pw

database_proxy = pw.DatabaseProxy()


class BaseModel(pw.Model):
    id = pw.UUIDField(primary_key=True, default=uuid.uuid4)
    created_at = pw.DateTimeField(default=datetime.utcnow)
    updated_at = pw.DateTimeField(default=datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)

    class Meta:
        database = database_proxy


class Document(BaseModel):
    user_id = pw.UUIDField(index=True)
    title = pw.CharField(max_length=500)
    content = pw.TextField(default="")
    file_type = pw.CharField(max_length=20, default="text")
    file_key = pw.CharField(max_length=500, null=True)  # MinIO object key
    char_count = pw.IntegerField(default=0)
    word_count = pw.IntegerField(default=0)
    status = pw.CharField(max_length=20, default="pending")  # pending | analyzing | done | error

    class Meta:
        table_name = "documents"


class AnalysisResult(BaseModel):
    document = pw.ForeignKeyField(Document, backref="analysis_results", on_delete="CASCADE")
    model_name = pw.CharField(max_length=100)
    label = pw.CharField(max_length=10)       # ai | human
    ai_score = pw.FloatField(default=0.0)
    human_score = pw.FloatField(default=0.0)
    confidence = pw.FloatField(default=0.0)
    threshold = pw.FloatField(default=0.5)
    highlight_spans = pw.TextField(default="[]")    # JSON
    linguistic_features = pw.TextField(default="{}")  # JSON
    explanations = pw.TextField(default="[]")       # JSON
    inference_ms = pw.FloatField(default=0.0)

    class Meta:
        table_name = "analysis_results"
