import urllib.parse
from typing import Tuple

import httpx
# pyrefly: ignore [missing-import]
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User


async def get_google_auth_url() -> str:
    """
    Constructs the Google OAuth2 authorization URL.
    """
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return url


async def exchange_google_code(code: str) -> dict:
    """
    Exchanges the authorization code for Google tokens.
    """
    data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient() as client:
        response = await client.post("https://oauth2.googleapis.com/token", data=data)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code with Google")
        return response.json()


async def get_google_user_info(access_token: str) -> dict:
    """
    Fetches user profile information from Google using the access token.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient() as client:
        response = await client.get("https://www.googleapis.com/oauth2/v3/userinfo", headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch user info from Google")
        return response.json()


async def upsert_user(db: AsyncSession, google_user_info: dict) -> User:
    """
    Creates or updates a user based on Google profile information.
    """
    google_id = google_user_info.get("sub")
    email = google_user_info.get("email")
    full_name = google_user_info.get("name")
    avatar_url = google_user_info.get("picture")

    if not google_id or not email:
        raise HTTPException(status_code=400, detail="Incomplete Google profile info")

    stmt = select(User).where(User.google_id == google_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # Update existing user
        user.email = email
        user.full_name = full_name
        user.avatar_url = avatar_url
    else:
        # Create new user
        user = User(
            google_id=google_id,
            email=email,
            full_name=full_name,
            avatar_url=avatar_url,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)
    return user


def generate_tokens(user: User) -> Tuple[str, str]:
    """
    Generates application JWT access and refresh tokens for a user.
    """
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))
    return access_token, refresh_token
