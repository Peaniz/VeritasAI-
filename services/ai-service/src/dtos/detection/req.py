from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    text: str
    model_name: str | None = None
    document_id: str | None = None


class AnalyzeBatchRequest(BaseModel):
    texts: list[str]
    model_name: str | None = None
