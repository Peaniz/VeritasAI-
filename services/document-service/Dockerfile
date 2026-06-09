FROM python:3.11-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv pip install --system --no-cache \
    fastapi "uvicorn[standard]" pydantic pydantic-settings \
    peewee psycopg2-binary redis confluent-kafka \
    grpcio grpcio-tools protobuf \
    minio python-multipart \
    "python-jose[cryptography]" httpx structlog

COPY . .

EXPOSE 8003 50053

CMD ["python", "main.py"]
