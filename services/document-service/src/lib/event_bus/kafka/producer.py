import json
import threading
from confluent_kafka import Producer
from src.settings import settings


class KafkaProducer:
    def __init__(self):
        self._producer = Producer({"bootstrap.servers": settings.kafka_bootstrap_servers})

    def publish(self, topic: str, key: str, value: dict) -> None:
        self._producer.produce(
            topic,
            key=key.encode(),
            value=json.dumps(value).encode(),
        )
        self._producer.poll(0)

    def flush(self) -> None:
        self._producer.flush()


_instance: KafkaProducer | None = None
_lock = threading.Lock()


def get_producer() -> KafkaProducer:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = KafkaProducer()
    return _instance
