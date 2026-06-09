from pydantic import BaseModel


class HighlightSpan(BaseModel):
    start: int
    end: int
    text: str
    ai_probability: float
    risk_level: str
    reasons: list[str]


class LinguisticFeatures(BaseModel):
    burstiness: float = 0.0
    ttr: float = 0.0
    bigram_rep_rate: float = 0.0
    word_entropy: float = 0.0
    func_word_ratio: float = 0.0
    sent_len_variation: float = 0.0
    punct_density: float = 0.0
    avg_word_len: float = 0.0
    mean_sent_len: float = 0.0
    std_sent_len: float = 0.0
    num_sentences: int = 0
    word_count: int = 0
    char_count: int = 0


class AnalyzeResponse(BaseModel):
    label: str
    ai_probability: float
    human_probability: float
    confidence: float
    threshold: float
    model_name: str
    linguistic_features: dict
    explanations: list[str]
    highlight_spans: list[HighlightSpan]
    inference_time_ms: float


class ModelInfo(BaseModel):
    name: str
    available: bool
    description: str
    f1_score: float


class ModelsResponse(BaseModel):
    models: list[ModelInfo]
    default_model: str
