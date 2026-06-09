FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

# Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 curl && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    rm -rf /var/lib/apt/lists/*

RUN python -m pip install uv

WORKDIR /app

COPY pyproject.toml .
RUN uv pip install --system --no-cache \
    fastapi "uvicorn[standard]" pydantic pydantic-settings \
    redis confluent-kafka \
    grpcio grpcio-tools protobuf \
    structlog httpx \
    torch --extra-index-url https://download.pytorch.org/whl/cu128 \
    transformers numpy scipy nltk

COPY . .

EXPOSE 8002 50052

CMD ["python", "main.py"]
