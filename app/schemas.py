from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ── Request ───────────────────────────────────────────────────────────────────

class DetectRequest(BaseModel):
    text:  str = Field(..., min_length=1, max_length=50_000, description="Text to analyse")
    model: str = Field("distilbert-base-uncased", description="Model key: distilbert-base-uncased | bert-base-uncased")


# ── Response ──────────────────────────────────────────────────────────────────

class LinguisticFeatures(BaseModel):
    burstiness:         float = 0.0
    num_sentences:      int   = 0
    mean_sent_len:      float = 0.0
    std_sent_len:       float = 0.0
    sent_len_variation: float = 0.0
    ttr:                float = 0.0
    avg_word_len:       float = 0.0
    punct_density:      float = 0.0
    func_word_ratio:    float = 0.0
    bigram_rep_rate:    float = 0.0
    word_entropy:       float = 0.0
    word_count:         int   = 0
    char_count:         int   = 0


class DetectResponse(BaseModel):
    label:               str
    ai_probability:      float
    human_probability:   float
    confidence:          float
    threshold:           float = 0.5
    model_name:          str
    inference_time_ms:   float
    linguistic_features: LinguisticFeatures | dict = {}
    explanations:        list[str]                 = []
    highlight_spans:     list[dict]                = []
    text_preview:        str                       = ""
    error:               Optional[str]             = None


# ── Model info ────────────────────────────────────────────────────────────────

class SliceMetric(BaseModel):
    slice_type:   str
    slice_name:   str
    n:            int
    accuracy:     float
    precision:    float
    recall:       float
    f1:           float
    auc_roc:      float
    tpr_at_fpr01: float
    tpr_at_fpr05: float = 1.0
    tpr_at_fpr10: float = 1.0


class ModelSpec(BaseModel):
    model_name:          str
    short_name:          str
    available:           bool
    # Performance
    accuracy:            float = 0.0
    precision:           float = 0.0
    recall:              float = 0.0
    f1:                  float = 0.0
    auc_roc:             float = 0.0
    tpr_at_fpr01:        float = 0.0
    tpr_at_fpr05:        float = 0.0
    tpr_at_fpr10:        float = 0.0
    test_loss:           float = 0.0
    # Size / speed
    num_parameters:      int   = 0
    model_size_mb:       float = 0.0
    avg_inference_ms:    float = 0.0
    threshold:           float = 0.5
    test_samples:        int   = 0
    # Confusion matrix  [[TN, FP], [FN, TP]]
    confusion_matrix:    list[list[int]] = []
    # Per-slice breakdown
    slice_metrics:       list[SliceMetric] = []
