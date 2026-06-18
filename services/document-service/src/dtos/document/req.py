from pydantic import BaseModel


class CreateDocumentRequest(BaseModel):
    title: str
    content: str
    file_type: str = "text"
    user_id: str  # passed from auth middleware / header
    model_name: str = "distilbert-base-uncased"
