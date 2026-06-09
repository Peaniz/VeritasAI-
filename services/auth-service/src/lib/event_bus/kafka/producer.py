import json
import threading
from confluent_kafka import Producer
from src.settings import settings
import structlog

log = structlog.get_logger()


class KafkaProducer:
    def __init__(self):
        self._producer = Producer(
            {"bootstrap.servers": settings.kafka_bootstrap_servers}
        )

    def publish(self, topic: str, key: str, value: dict) -> None:
        def delivery_report(err, msg):
            if err:
                log.error("kafka_delivery_failed", topic=topic, error=str(err))

        self._producer.produce(
            topic,
            key=key.encode("utf-8"),
            value=json.dumps(value).encode("utf-8"),
            callback=delivery_report,
        )
        self._producer.poll(0)

    def flush(self) -> None:
        self._producer.flush()


_producer_instance: KafkaProducer | None = None
_lock = threading.Lock()


def get_producer() -> KafkaProducer:
    global _producer_instance
    if _producer_instance is None:
        with _lock:
            if _producer_instance is None:
                _producer_instance = KafkaProducer()
    return _producer_instance
