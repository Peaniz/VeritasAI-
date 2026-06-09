import json
import threading
from confluent_kafka import Consumer, KafkaError
from src.settings import settings
import structlog

log = structlog.get_logger()


class KafkaWorker:
    def __init__(self, analytics_svc):
        self.svc = analytics_svc
        self._running = False
        self._thread: threading.Thread | None = None
        self._consumer = Consumer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.kafka_group_id,
            "auto.offset.reset": "earliest",
        })

    def _run(self) -> None:
        topics = ["user.registered", "user.login", "document.created", "analysis.completed", "usage.tracked"]
        self._consumer.subscribe(topics)
        log.info("analytics_worker_started", topics=topics)

        while self._running:
            msg = self._consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                log.error("kafka_error", error=str(msg.error()))
                continue

            try:
                event = json.loads(msg.value().decode("utf-8"))
                topic = msg.topic()
                self._dispatch(topic, event)
            except Exception as exc:
                log.error("analytics_processing_failed", error=str(exc))

        self._consumer.close()

    def _dispatch(self, topic: str, event: dict) -> None:
        user_id = event.get("user_id")

        if topic == "user.registered":
            self.svc.record_event("user.registered", user_id, event)
        elif topic == "user.login":
            self.svc.record_event("user.login", user_id, event)
        elif topic == "document.created":
            self.svc.record_event("document.created", user_id, event)
        elif topic == "analysis.completed":
            self.svc.record_event("analysis.completed", user_id, event)
            label = event.get("label", "unknown")
            ai_score = event.get("ai_probability", 0.0)
            char_count = event.get("linguistic_features", {}).get("char_count", 0)
            if user_id:
                self.svc.upsert_daily_stat(user_id, label, ai_score, char_count)
        elif topic == "usage.tracked":
            self.svc.record_event("usage.tracked", user_id, event)

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
