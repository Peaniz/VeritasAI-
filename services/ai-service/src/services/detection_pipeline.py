"""
AI Content Detector - Enhanced version for ai-service.
Supports multiple models (DistilBERT + BERT), GPU inference, explainability.
"""

import os
import re
import json
import math
import time
import string
import numpy as np
import torch
from collections import Counter
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import structlog

log = structlog.get_logger()

_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_HTML_RE = re.compile(r"<[^>]+>")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]")
_MULTI_SPACE_RE = re.compile(r"\s{2,}")
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

_ENGLISH_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "shall", "can", "need", "dare", "ought", "used", "it", "its",
    "this", "that", "these", "those", "i", "you", "he", "she", "we", "they",
    "me", "him", "her", "us", "them", "my", "your", "his", "our", "their",
    "not", "no", "nor", "so", "yet", "both", "either", "neither", "each",
    "as", "if", "than", "then", "when", "where", "while", "after", "before",
    "what", "which", "who", "whom", "how", "about", "above", "up", "down",
    "into", "through", "during", "just", "more", "also", "very", "too",
})


def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = _URL_RE.sub(" ", text)
    text = _HTML_RE.sub(" ", text)
    text = _CONTROL_RE.sub(" ", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    return text.strip()


def _sentence_spans(text: str) -> list[tuple[int, int, str]]:
    spans = []
    for m in re.finditer(r"[^.!?]+[.!?]*\s*", text):
        s = m.group(0)
        core = s.strip()
        if not core:
            continue
        spans.append((m.start(), m.start() + len(s), core))
    if not spans and text.strip():
        spans = [(0, len(text), text.strip())]
    return spans


def compute_linguistic_features(text: str) -> dict:
    words_raw = text.lower().split()
    n_words = len(words_raw)
    n_chars = len(text)

    if n_words == 0:
        return {k: 0 for k in [
            "burstiness", "num_sentences", "mean_sent_len", "std_sent_len",
            "sent_len_variation", "ttr", "avg_word_len", "punct_density",
            "func_word_ratio", "bigram_rep_rate", "word_entropy",
            "word_count", "char_count",
        ]}

    sentences = _SENT_SPLIT_RE.split(text.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 0]
    num_sentences = len(sentences)
    if num_sentences > 0:
        lengths = [len(s.split()) for s in sentences]
        mean_sent_len = float(np.mean(lengths))
        std_sent_len = float(np.std(lengths))
        sent_len_variation = std_sent_len / mean_sent_len if mean_sent_len > 0 else 0.0
    else:
        mean_sent_len = std_sent_len = sent_len_variation = 0.0

    freq = Counter(words_raw)
    counts = np.array(list(freq.values()), dtype=np.float64)
    mean_c, std_c = np.mean(counts), np.std(counts)
    burstiness = float((std_c - mean_c) / (std_c + mean_c)) if (std_c + mean_c) > 0 else 0.0

    ttr = len(set(words_raw)) / n_words
    avg_word_len = float(np.mean([len(w) for w in words_raw]))
    n_punct = sum(1 for ch in text if ch in string.punctuation)
    punct_density = n_punct / n_chars if n_chars > 0 else 0.0
    func_word_ratio = sum(1 for w in words_raw if w in _ENGLISH_STOPWORDS) / n_words

    if n_words >= 2:
        bigrams = [(words_raw[i], words_raw[i + 1]) for i in range(n_words - 1)]
        bigram_freq = Counter(bigrams)
        repeated = sum(1 for cnt in bigram_freq.values() if cnt > 1)
        bigram_rep_rate = repeated / len(bigrams)
    else:
        bigram_rep_rate = 0.0

    total = sum(freq.values())
    entropy = -sum((c / total) * math.log2(c / total) for c in freq.values() if c > 0)
    n_unique = len(freq)
    max_entropy = math.log2(n_unique) if n_unique > 1 else 1.0
    word_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

    return {
        "burstiness": round(burstiness, 4),
        "num_sentences": num_sentences,
        "mean_sent_len": round(mean_sent_len, 2),
        "std_sent_len": round(std_sent_len, 2),
        "sent_len_variation": round(sent_len_variation, 4),
        "ttr": round(float(ttr), 4),
        "avg_word_len": round(float(avg_word_len), 2),
        "punct_density": round(float(punct_density), 4),
        "func_word_ratio": round(float(func_word_ratio), 4),
        "bigram_rep_rate": round(float(bigram_rep_rate), 4),
        "word_entropy": round(float(word_entropy), 4),
        "word_count": n_words,
        "char_count": n_chars,
    }


class SingleModelDetector:
    """Wraps one fine-tuned transformer model for AI detection."""

    def __init__(self, model_dir: str, max_length: int = 256, device: str = "cpu"):
        self.model_dir = model_dir
        self.model_name = os.path.basename(model_dir)
        self.max_length = max_length
        self.device = device

        log.info("loading_model", model=self.model_name, device=device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir)
        self.model.to(device)
        self.model.eval()

        threshold_path = os.path.join(model_dir, "threshold.json")
        if os.path.exists(threshold_path):
            with open(threshold_path) as f:
                data = json.load(f)
            self.threshold = float(data.get("threshold", 0.5))
        else:
            self.threshold = 0.5

        # Load training history metadata if available
        history_path = os.path.join(model_dir, "training_history.json")
        self.metadata: dict = {}
        if os.path.exists(history_path):
            with open(history_path) as f:
                hist = json.load(f)
            if isinstance(hist, list) and hist:
                last = hist[-1]
                self.metadata = {
                    "f1": last.get("val_f1", 0.0),
                    "auroc": last.get("val_auroc", 0.0),
                }

        log.info("model_loaded", model=self.model_name, threshold=self.threshold)

    def predict_proba(self, text: str) -> tuple[float, float]:
        """Returns (ai_prob, human_prob)."""
        enc = self.tokenizer(
            text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        ).to(self.device)
        with torch.no_grad():
            logits = self.model(**enc).logits
            probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]
        return float(probs[1]), float(probs[0])


class AIDetectionPipeline:
    """
    Multi-model AI content detection pipeline.

    Loads available models from models_dir at startup.
    Primary: distilbert-base-uncased (F1=0.9969)
    Secondary: bert-base-uncased (loaded only if model.safetensors exists)
    """

    _instance: "AIDetectionPipeline | None" = None

    def __init__(self, models_dir: str, default_model: str, max_length: int = 256):
        self.models_dir = models_dir
        self.default_model = default_model
        self.max_length = max_length
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._models: dict[str, SingleModelDetector] = {}

        # Load comparison results for full model stats
        self._comparison: dict[str, dict] = {}
        comp_path = os.path.join(models_dir, "comparison_results.json")
        if os.path.exists(comp_path):
            try:
                with open(comp_path) as f:
                    for entry in json.load(f):
                        self._comparison[entry["model_name"]] = entry
                log.info("comparison_results_loaded", count=len(self._comparison))
            except Exception as exc:
                log.warning("comparison_results_load_failed", error=str(exc))

        log.info("detection_pipeline_init", device=self.device)

    def load_models(self) -> None:
        if not os.path.isdir(self.models_dir):
            log.warning("models_dir_not_found", path=self.models_dir)
            return

        for model_name in os.listdir(self.models_dir):
            model_dir = os.path.join(self.models_dir, model_name)
            if not os.path.isdir(model_dir):
                continue
            # Only load models that have weights
            has_weights = (
                os.path.exists(os.path.join(model_dir, "model.safetensors"))
                or os.path.exists(os.path.join(model_dir, "pytorch_model.bin"))
            )
            if not has_weights:
                log.warning("model_weights_missing_skipping", model=model_name)
                continue
            try:
                self._models[model_name] = SingleModelDetector(
                    model_dir=model_dir,
                    max_length=self.max_length,
                    device=self.device,
                )
            except Exception as exc:
                log.error("model_load_failed", model=model_name, error=str(exc))

        log.info("models_available", models=list(self._models.keys()))

    def available_models(self) -> list[dict]:
        result = []
        for name, m in self._models.items():
            comp = self._comparison.get(name, {})
            result.append({
                "name": name,
                "available": True,
                "description": "Fine-tuned transformer for AI content detection",
                "f1_score": comp.get("f1", m.metadata.get("f1", 0.0)),
            })
        return result

    def available_models_full(self) -> list[dict]:
        """Return full model specs including comparison results data for the frontend."""
        result = []
        for name, m in self._models.items():
            comp = self._comparison.get(name, {})
            result.append({
                "model_name": name,
                "short_name": name.split("-")[0].title(),
                "available": True,
                "accuracy": comp.get("accuracy", 0.0),
                "precision": comp.get("precision", 0.0),
                "recall": comp.get("recall", 0.0),
                "f1": comp.get("f1", m.metadata.get("f1", 0.0)),
                "auc_roc": comp.get("auc_roc", 0.0),
                "tpr_at_fpr01": comp.get("tpr_at_fpr01", 0.0),
                "num_parameters": comp.get("num_parameters", 0),
                "model_size_mb": comp.get("model_size_mb", 0.0),
                "avg_inference_ms": comp.get("avg_inference_ms", 0.0),
                "threshold": m.threshold,
                "confusion_matrix": comp.get("confusion_matrix", [[0, 0], [0, 0]]),
                "slice_metrics": comp.get("slice_metrics", []),
            })
        return result

    def _get_model(self, model_name: str | None) -> SingleModelDetector:
        name = model_name or self.default_model
        if name not in self._models:
            if not self._models:
                raise RuntimeError("No models are loaded")
            name = next(iter(self._models))
        return self._models[name]

    def _sentence_reasons(self, sentence: str, local_feat: dict) -> list[str]:
        reasons = []
        words = sentence.lower().split()
        n = len(words)
        if local_feat.get("ttr", 1.0) < 0.55 and n >= 12:
            reasons.append("High lexical repetition (low lexical diversity)")
        if local_feat.get("bigram_rep_rate", 0.0) > 0.08:
            reasons.append("Repeated phrase patterns (high bigram repetition)")
        if local_feat.get("sent_len_variation", 1.0) < 0.2:
            reasons.append("Sentence rhythm is overly uniform")
        if local_feat.get("func_word_ratio", 0.0) > 0.48:
            reasons.append("High function-word ratio (typical of AI text)")
        if local_feat.get("word_entropy", 1.0) < 0.72 and n >= 12:
            reasons.append("Low word diversity (low word entropy)")
        if local_feat.get("punct_density", 0.0) < 0.02 and n >= 20:
            reasons.append("Unusually low punctuation density")
        if not reasons:
            reasons.append("Higher-than-average AI probability for this sentence")
        return reasons[:3]

    def _explain_spans(
        self, raw_text: str, model: SingleModelDetector, full_ai_prob: float
    ) -> tuple[list[dict], list[str]]:
        spans = _sentence_spans(raw_text)
        explained = []
        ai_scores = []

        for start, end, sentence in spans:
            cleaned = clean_text(sentence)
            if len(cleaned) < 8:
                continue
            ai_prob, _ = model.predict_proba(cleaned)
            local_feat = compute_linguistic_features(cleaned)

            if ai_prob >= 0.80:
                level = "high"
            elif ai_prob >= 0.55:
                level = "medium"
            else:
                level = "low"

            explained.append({
                "start": start,
                "end": end,
                "text": sentence,
                "ai_probability": round(ai_prob, 4),
                "risk_level": level,
                "reasons": self._sentence_reasons(sentence, local_feat),
            })
            ai_scores.append(ai_prob)

        summary = []
        if ai_scores:
            high = sum(1 for p in ai_scores if p >= 0.75)
            medium = sum(1 for p in ai_scores if 0.55 <= p < 0.75)
            if high > 0:
                summary.append(f"{high} sentence(s) are high AI risk (red)")
            if medium > 0:
                summary.append(f"{medium} sentence(s) are medium AI risk (yellow)")
            if full_ai_prob >= model.threshold:
                summary.append("Overall probability is above the calibrated AI threshold")
        return explained, summary

    def analyze(self, text: str, model_name: str | None = None) -> dict:
        t0 = time.time()
        model = self._get_model(model_name)
        cleaned = clean_text(text)

        if len(cleaned) < 10:
            return {
                "label": "unknown",
                "ai_probability": 0.0,
                "human_probability": 0.0,
                "confidence": 0.0,
                "threshold": model.threshold,
                "model_name": model.model_name,
                "linguistic_features": {},
                "explanations": ["Text too short to analyze"],
                "highlight_spans": [],
                "inference_time_ms": 0.0,
            }

        ling = compute_linguistic_features(cleaned)
        ai_prob, human_prob = model.predict_proba(cleaned)
        label = "ai" if ai_prob >= model.threshold else "human"
        confidence = max(ai_prob, human_prob)
        spans, summary = self._explain_spans(text, model, ai_prob)
        elapsed = (time.time() - t0) * 1000

        return {
            "label": label,
            "ai_probability": round(ai_prob, 4),
            "human_probability": round(human_prob, 4),
            "confidence": round(confidence, 4),
            "threshold": round(model.threshold, 3),
            "model_name": model.model_name,
            "linguistic_features": ling,
            "explanations": summary,
            "highlight_spans": spans,
            "inference_time_ms": round(elapsed, 2),
        }

    def analyze_batch(self, texts: list[str], model_name: str | None = None) -> list[dict]:
        return [self.analyze(t, model_name) for t in texts]
