import grpc
from concurrent import futures
from src.settings import settings
import structlog

log = structlog.get_logger()

try:
    from src.grpc_generated import detection_pb2, detection_pb2_grpc
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False


class DetectionServicer:
    def __init__(self, pipeline):
        self.pipeline = pipeline

    def Analyze(self, request, context):
        if not GRPC_AVAILABLE:
            context.abort(grpc.StatusCode.UNAVAILABLE, "gRPC stubs not generated")
            return

        result = self.pipeline.analyze(request.text, request.model_name or None)

        ling = result.get("linguistic_features", {})
        ling_msg = detection_pb2.LinguisticFeatures(
            burstiness=ling.get("burstiness", 0.0),
            ttr=ling.get("ttr", 0.0),
            bigram_rep_rate=ling.get("bigram_rep_rate", 0.0),
            word_entropy=ling.get("word_entropy", 0.0),
            func_word_ratio=ling.get("func_word_ratio", 0.0),
            sent_len_variation=ling.get("sent_len_variation", 0.0),
            punct_density=ling.get("punct_density", 0.0),
            avg_word_len=ling.get("avg_word_len", 0.0),
            mean_sent_len=ling.get("mean_sent_len", 0.0),
            std_sent_len=ling.get("std_sent_len", 0.0),
            num_sentences=ling.get("num_sentences", 0),
            word_count=ling.get("word_count", 0),
            char_count=ling.get("char_count", 0),
        )

        spans = [
            detection_pb2.HighlightSpan(
                start=s["start"],
                end=s["end"],
                risk_level=s["risk_level"],
                sentence=s["text"],
                ai_probability=s["ai_probability"],
                reasons=s["reasons"],
            )
            for s in result.get("highlight_spans", [])
        ]

        return detection_pb2.AnalyzeResponse(
            label=result["label"],
            ai_probability=result["ai_probability"],
            human_probability=result["human_probability"],
            confidence=result["confidence"],
            threshold=result["threshold"],
            model_name=result["model_name"],
            linguistic_features=ling_msg,
            highlight_spans=spans,
            inference_time_ms=result["inference_time_ms"],
        )

    def GetAvailableModels(self, request, context):
        if not GRPC_AVAILABLE:
            context.abort(grpc.StatusCode.UNAVAILABLE, "gRPC stubs not generated")
            return
        models = self.pipeline.available_models()
        return detection_pb2.ModelsResponse(
            models=[
                detection_pb2.ModelInfo(
                    name=m["name"],
                    available=m["available"],
                    description=m["description"],
                    f1_score=m["f1_score"],
                )
                for m in models
            ],
            default_model=settings.default_model,
        )

    def AnalyzeBatch(self, request, context):
        if not GRPC_AVAILABLE:
            context.abort(grpc.StatusCode.UNAVAILABLE, "gRPC stubs not generated")
            return
        results = self.pipeline.analyze_batch(list(request.texts), request.model_name or None)
        responses = []
        for r in results:
            ling = r.get("linguistic_features", {})
            ling_msg = detection_pb2.LinguisticFeatures(**{
                k: ling.get(k, 0) for k in [
                    "burstiness", "ttr", "bigram_rep_rate", "word_entropy",
                    "func_word_ratio", "sent_len_variation", "punct_density",
                    "avg_word_len", "mean_sent_len", "std_sent_len",
                    "num_sentences", "word_count", "char_count",
                ]
            })
            responses.append(detection_pb2.AnalyzeResponse(
                label=r["label"],
                ai_probability=r["ai_probability"],
                human_probability=r["human_probability"],
                confidence=r["confidence"],
                threshold=r["threshold"],
                model_name=r["model_name"],
                linguistic_features=ling_msg,
                inference_time_ms=r["inference_time_ms"],
            ))
        return detection_pb2.AnalyzeBatchResponse(results=responses)


def serve_grpc(pipeline):
    if not GRPC_AVAILABLE:
        log.warning("grpc_stubs_missing_run_make_proto")
        return None

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = DetectionServicer(pipeline)
    detection_pb2_grpc.add_DetectionServiceServicer_to_server(servicer, server)
    server.add_insecure_port(f"[::]:{settings.grpc_port}")
    server.start()
    log.info("grpc_server_started", port=settings.grpc_port)
    return server
