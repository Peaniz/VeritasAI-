import enum
import datetime
import peewee as pw
from src.shared.base_entity import BaseModel


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class UserPlan(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(BaseModel):
    email = pw.CharField(max_length=255, unique=True, index=True)
    # password_hash is nullable: Google OAuth users have no password
    password_hash = pw.CharField(max_length=255, null=True)
    full_name = pw.CharField(max_length=255)
    avatar_url = pw.CharField(max_length=512, null=True)
    role = pw.CharField(max_length=20, default=UserRole.USER.value)
    plan = pw.CharField(max_length=20, default=UserPlan.FREE.value)
    is_verified = pw.BooleanField(default=False)

    # ── Google OAuth ─────────────────────────────────────────────────────
    google_id = pw.CharField(max_length=128, null=True, unique=True, index=True)

    # ── Stripe Billing ───────────────────────────────────────────────────
    stripe_customer_id = pw.CharField(max_length=128, null=True, unique=True, index=True)
    stripe_subscription_id = pw.CharField(max_length=128, null=True)
    stripe_subscription_status = pw.CharField(max_length=32, null=True)  # active / canceled / past_due

    # ── Usage Quota ──────────────────────────────────────────────────────
    analyses_today = pw.IntegerField(default=0)
    analyses_reset_date = pw.DateField(default=datetime.date.today)
    preferences = pw.TextField(default='{"default_model": "distilbert-base-uncased", "auto_save": true, "language": "en"}')

    class Meta:
        table_name = "users"


class RefreshToken(BaseModel):
    user = pw.ForeignKeyField(User, backref="refresh_tokens", on_delete="CASCADE")
    token_hash = pw.CharField(max_length=255, index=True)
    expires_at = pw.DateTimeField()
    revoked = pw.BooleanField(default=False)

    class Meta:
        table_name = "refresh_tokens"


class GoogleOAuthState(BaseModel):
    """Short-lived CSRF state tokens for Google OAuth flow."""
    state = pw.CharField(max_length=128, unique=True, index=True)
    expires_at = pw.DateTimeField()
    used = pw.BooleanField(default=False)

    class Meta:
        table_name = "google_oauth_states"
