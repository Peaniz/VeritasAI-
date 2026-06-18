from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "analytics-service"
    app_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8004

    database_url: str = "postgresql://veritasai:veritasai_secret_2026@localhost/analytics_db"
    redis_url: str = "redis://localhost:6379/1"
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_group_id: str = "analytics-service"

    grpc_port: int = 50054

    jwt_secret: str = "super_secret_jwt_key_change_in_production_32chars"
    jwt_algorithm: str = "HS256"


settings = Settings()
