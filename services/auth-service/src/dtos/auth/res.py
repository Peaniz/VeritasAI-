from pydantic import BaseModel


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    avatar_url: str | None = None
    role: str
    plan: str
    is_verified: bool
    has_google: bool = False      # True if Google OAuth linked
    analyses_today: int = 0
    created_at: str


class RegisterResponse(BaseModel):
    user: UserOut
    tokens: TokenPair


class LoginResponse(BaseModel):
    user: UserOut
    tokens: TokenPair


class RefreshResponse(BaseModel):
    tokens: TokenPair
