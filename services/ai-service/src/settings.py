from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ai-service"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8002

    redis_url: str = "redis://localhost:6379/0"
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_group_id: str = "ai-service"

    models_dir: str = "./models"
    default_model: str = "distilbert-base-uncased"
    max_text_length: int = 10000

    grpc_port: int = 50052
    auth_grpc_host: str = "localhost"
    auth_grpc_port: int = 50051


settings = Settings()
