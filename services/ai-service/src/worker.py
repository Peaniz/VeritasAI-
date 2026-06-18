"""Kafka consumer: listens to document.created, triggers analysis, publishes analysis.completed."""

import json
import socket
import threading
from src.settings import settings
import structlog

log = structlog.get_logger()


def _kafka_reachable(bootstrap_servers: str, timeout: float = 3.0) -> bool:
    """Quick TCP check — returns True if at least one broker is reachable."""
    for server in bootstrap_servers.split(","):
        host, _, port_str = server.strip().rpartition(":")
        host = host or "localhost"
        port = int(port_str) if port_str.isdigit() else 9092
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            pass
    return False


class KafkaWorker:
    def __init__(self, pipeline):
        self.pipeline = pipeline
        self._running = False
        self._thread: threading.Thread | None = None
        self._enabled = False  # set to True only if Kafka is reachable

    def _make_consumer(self):
        from confluent_kafka import Consumer
        return Consumer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.kafka_group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
            "socket.timeout.ms": 10000,
            "session.timeout.ms": 30000,
            "reconnect.backoff.max.ms": 10000,
            "log_level": 3,          # 3=warning, suppress debug noise
        })

    def _make_producer(self):
        from confluent_kafka import Producer
        return Producer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "socket.timeout.ms": 10000,
            "message.timeout.ms": 10000,
            "log_level": 3,
        })

    def _handle_document_created(self, event: dict) -> None:
        doc_id = event.get("document_id")
        user_id = event.get("user_id")
        text = event.get("content", "")
        model_name = event.get("model_name", settings.default_model)

        if not doc_id or not text:
            log.warning("kafka_event_missing_fields", event=event)
            return

        log.info("analyzing_document", document_id=doc_id)
        try:
            result = self.pipeline.analyze(text, model_name)
        except Exception as exc:
            log.error("analysis_failed", document_id=doc_id, error=str(exc))
            return

        payload = {
            "document_id": doc_id,
            "user_id": user_id,
            "label": result["label"],
            "ai_probability": result["ai_probability"],
            "human_probability": result["human_probability"],
            "confidence": result["confidence"],
            "threshold": result["threshold"],
            "model_name": result["model_name"],
            "linguistic_features": result["linguistic_features"],
            "highlight_spans": result["highlight_spans"],
            "explanations": result["explanations"],
            "inference_time_ms": result["inference_time_ms"],
        }

        try:
            producer = self._make_producer()
            producer.produce(
                "analysis.completed",
                key=doc_id.encode(),
                value=json.dumps(payload).encode(),
            )
            producer.flush(timeout=5)
            log.info("analysis_completed_published", document_id=doc_id, label=result["label"])
        except Exception as exc:
            log.warning("kafka_produce_failed", document_id=doc_id, error=str(exc))

    def _run(self) -> None:
        import time
        from confluent_kafka import KafkaError
        retry_delay = 10
        consumer = None

        while self._running:
            try:
                consumer = self._make_consumer()
                consumer.subscribe(["document.created"])
                log.info("kafka_consumer_subscribed", topics=["document.created"])

                while self._running:
                    msg = consumer.poll(timeout=2.0)
                    if msg is None:
                        continue
                    if msg.error():
                        err = msg.error()
                        if err.code() == KafkaError._PARTITION_EOF:
                            continue
                        if err.fatal():
                            log.warning("kafka_fatal_error_will_reconnect", error=str(err))
                            break
                        # Non-fatal: log and keep polling
                        log.warning("kafka_consumer_warning", error=str(err))
                        continue

                    try:
                        event = json.loads(msg.value().decode("utf-8"))
                        if msg.topic() == "document.created":
                            self._handle_document_created(event)
                    except Exception as exc:
                        log.warning("kafka_message_processing_failed", error=str(exc))

            except Exception as exc:
                log.warning("kafka_worker_exception", error=str(exc))
            finally:
                if consumer is not None:
                    try:
                        consumer.close()
                    except Exception:
                        pass
                    consumer = None

            if self._running:
                log.info("kafka_worker_sleeping_before_retry", delay=retry_delay)
                time.sleep(retry_delay)

        log.info("kafka_worker_stopped")

    def start(self) -> None:
        if not _kafka_reachable(settings.kafka_bootstrap_servers):
            log.warning("kafka_not_reachable_worker_disabled",
                        servers=settings.kafka_bootstrap_servers)
            return
        self._enabled = True
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        log.info("kafka_worker_started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
