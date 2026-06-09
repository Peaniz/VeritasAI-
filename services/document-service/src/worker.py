"""Kafka consumer: listens to analysis.completed, saves results to DB."""

import json
import threading
from confluent_kafka import Consumer, KafkaError
from src.settings import settings
import structlog

log = structlog.get_logger()


class KafkaWorker:
    def __init__(self, doc_service):
        self.doc_svc = doc_service
        self._running = False
        self._thread: threading.Thread | None = None
        self._consumer = Consumer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.kafka_group_id,
            "auto.offset.reset": "earliest",
        })

    def _handle_analysis_completed(self, event: dict) -> None:
        doc_id = event.get("document_id")
        if not doc_id:
            return
        try:
            self.doc_svc.save_analysis_result(doc_id, event)
        except Exception as exc:
            log.error("save_analysis_failed", doc_id=doc_id, error=str(exc))

    def _run(self) -> None:
        self._consumer.subscribe(["analysis.completed"])
        log.info("document_kafka_worker_started")

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
                self._handle_analysis_completed(event)
            except Exception as exc:
                log.error("kafka_processing_failed", error=str(exc))

        self._consumer.close()

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
