import base64
import hashlib
from datetime import datetime, timedelta
from typing import Optional
import bcrypt as _bcrypt
from jose import JWTError, jwt
from src.settings import settings
from src.entities.user import User, RefreshToken


def _password_to_bytes(password: str) -> bytes:
    """SHA-256 prehash → base64 (44 bytes). Bypasses bcrypt's 72-byte limit entirely."""
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(_password_to_bytes(password), _bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(_password_to_bytes(plain), hashed.encode("ascii"))


def create_access_token(user_id: str, email: str, role: str, plan: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "plan": plan,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    def register(self, email: str, password: str, full_name: str) -> tuple[User, str, str]:
        if User.select().where(User.email == email).exists():
            raise ValueError("Email already registered")

        user = User.create(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
        )

        access_token = create_access_token(
            str(user.id), user.email, user.role, user.plan
        )
        refresh_token = create_refresh_token(str(user.id))

        RefreshToken.create(
            user=user,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days),
        )

        return user, access_token, refresh_token

    def login(self, email: str, password: str) -> tuple[User, str, str]:
        user = User.get_or_none(User.email == email)
        if not user or not verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")

        access_token = create_access_token(
            str(user.id), user.email, user.role, user.plan
        )
        refresh_token = create_refresh_token(str(user.id))

        RefreshToken.create(
            user=user,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days),
        )

        return user, access_token, refresh_token

    def refresh(self, refresh_token: str) -> tuple[str, str]:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token")

        token_record = RefreshToken.get_or_none(
            RefreshToken.token_hash == hash_token(refresh_token),
            RefreshToken.revoked == False,
        )
        if not token_record:
            raise ValueError("Refresh token not found or revoked")

        if token_record.expires_at < datetime.utcnow():
            raise ValueError("Refresh token expired")

        token_record.revoked = True
        token_record.save()

        user = token_record.user
        new_access = create_access_token(str(user.id), user.email, user.role, user.plan)
        new_refresh = create_refresh_token(str(user.id))

        RefreshToken.create(
            user=user,
            token_hash=hash_token(new_refresh),
            expires_at=datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days),
        )

        return new_access, new_refresh

    def validate_token(self, token: str) -> Optional[dict]:
        return decode_token(token)

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        return User.get_or_none(User.id == user_id)

    def update_profile(self, user: User, full_name: str) -> User:
        user.full_name = full_name.strip()
        user.save()
        return user
