from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "auth-service"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8001
    frontend_url: str = "http://localhost"

    # Database
    database_url: str = "postgresql://veritasai:veritasai_secret_2026@localhost/auth_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_group_id: str = "auth-service"

    # JWT
    jwt_secret: str = "super_secret_jwt_key_change_in_production_32chars"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # gRPC
    grpc_port: int = 50051

    # ── Google OAuth 2.0 ─────────────────────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost/auth/google/callback"

    # ── Stripe Billing ────────────────────────────────────────────────────────
    stripe_secret_key: str = ""         # sk_test_... or sk_live_...
    stripe_publishable_key: str = ""    # pk_test_... or pk_live_...
    stripe_webhook_secret: str = ""     # whsec_...
    stripe_pro_price_id: str = ""       # price_... for Pro monthly
    stripe_enterprise_price_id: str = "" # price_... for Enterprise monthly

    # ── Subscription Plan Quotas ──────────────────────────────────────────────
    free_daily_limit: int = 10
    free_max_chars: int = 2_000
    pro_daily_limit: int = 500
    pro_max_chars: int = 10_000
    enterprise_daily_limit: int = 0     # 0 = unlimited
    enterprise_max_chars: int = 50_000


settings = Settings()
