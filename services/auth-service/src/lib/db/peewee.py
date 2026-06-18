import peewee as pw
from src.settings import settings
import structlog

log = structlog.get_logger()


def get_db() -> pw.PostgresqlDatabase:
    return pw.PostgresqlDatabase(None)


def _run_migrations(db: pw.PostgresqlDatabase) -> None:
    """
    Safe incremental migrations: add columns that don't exist yet.
    Uses raw SQL so we can run IF NOT EXISTS checks.
    """
    migrations = [
        # New nullable columns on existing 'users' table
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR(128)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(128)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(128)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_status VARCHAR(32)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS analyses_today INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS analyses_reset_date DATE DEFAULT CURRENT_DATE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences TEXT DEFAULT '{\"default_model\": \"distilbert-base-uncased\", \"auto_save\": true, \"language\": \"en\"}'",
        # Allow password_hash to be NULL (Google-only accounts)
        "ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL",
        # Unique indexes (CREATE UNIQUE INDEX IF NOT EXISTS is safe to re-run)
        "CREATE UNIQUE INDEX IF NOT EXISTS users_google_id_key ON users (google_id) WHERE google_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS users_stripe_customer_id_key ON users (stripe_customer_id) WHERE stripe_customer_id IS NOT NULL",
    ]
    for sql in migrations:
        try:
            db.execute_sql(sql)
        except Exception as e:
            log.warning("migration_skipped", sql=sql[:60], error=str(e))


def init_db() -> pw.PostgresqlDatabase:
    db_url = settings.database_url
    import urllib.parse
    parsed = urllib.parse.urlparse(db_url)
    db = pw.PostgresqlDatabase(
        parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname,
        port=parsed.port or 5432,
    )

    from src.shared.base_entity import database_proxy
    database_proxy.initialize(db)

    db.connect(reuse_if_open=True)

    # Step 1: Run column migrations on existing tables
    _run_migrations(db)

    # Step 2: Create new tables (safe=True skips existing ones)
    from src.entities.user import User, RefreshToken, GoogleOAuthState
    db.create_tables([User, RefreshToken, GoogleOAuthState], safe=True)

    log.info("database_initialized")
    return db
