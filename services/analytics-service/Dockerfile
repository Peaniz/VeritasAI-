FROM python:3.11-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml .
RUN uv pip install --system --no-cache \
    fastapi "uvicorn[standard]" pydantic pydantic-settings \
    peewee psycopg2-binary redis confluent-kafka structlog
COPY . .
EXPOSE 8004
CMD ["python", "main.py"]
