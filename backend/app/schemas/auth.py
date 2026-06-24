from typing import Optional

from pydantic import BaseModel


class GoogleAuthURL(BaseModel):
    auth_url: str


class GoogleCallback(BaseModel):
    code: str
    state: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str
