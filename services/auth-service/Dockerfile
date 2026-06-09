FROM python:3.11-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv pip install --system --no-cache \
        fastapi "uvicorn[standard]" "pydantic[email]" pydantic-settings \
        peewee psycopg2-binary redis confluent-kafka \
        grpcio grpcio-tools protobuf \
        "python-jose[cryptography]" "passlib[bcrypt]" \
        python-multipart httpx structlog email-validator \
        stripe

COPY . .

EXPOSE 8001 50051

CMD ["python", "main.py"]
