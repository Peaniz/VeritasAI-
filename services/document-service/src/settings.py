from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "document-service"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8003

    database_url: str = "postgresql://veritasai:veritasai_secret_2026@localhost/document_db"
    redis_url: str = "redis://localhost:6379/0"
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_group_id: str = "document-service"

    minio_endpoint: str = "localhost:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin123"
    minio_bucket: str = "veritasai-documents"
    minio_secure: bool = False

    ai_grpc_host: str = "localhost"
    ai_grpc_port: int = 50052
    auth_grpc_host: str = "localhost"
    auth_grpc_port: int = 50051

    jwt_secret: str = "super_secret_jwt_key_change_in_production_32chars"
    jwt_algorithm: str = "HS256"

    grpc_port: int = 50053

    auth_service_url: str = "http://localhost:8001"


settings = Settings()
