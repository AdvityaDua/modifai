from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import GoogleAuthURL, GoogleCallback, RefreshTokenRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services import auth_service

router = APIRouter()


@router.get("/google/login", response_model=GoogleAuthURL)
async def google_login():
    """
    Returns the Google OAuth2 authorization URL.
    """
    url = await auth_service.get_google_auth_url()
    return GoogleAuthURL(auth_url=url)


@router.post("/google/callback", response_model=TokenResponse)
async def google_callback(payload: GoogleCallback, db: AsyncSession = Depends(get_db)):
    """
    Callback endpoint to exchange the authorization code for JWT tokens.
    """
    # 1. Exchange code for Google tokens
    token_data = await auth_service.exchange_google_code(payload.code)
    
    # 2. Fetch user profile from Google
    user_info = await auth_service.get_google_user_info(token_data["access_token"])
    
    # 3. Upsert user in our database
    user = await auth_service.upsert_user(db, user_info)
    
    # 4. Generate application JWTs
    access_token, refresh_token = auth_service.generate_tokens(user)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=3600
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """
    Refresh an expired access token using a valid refresh token.
    """
    from app.core.security import decode_token
    from app.services.user_service import get_user_by_id
    from jose import JWTError

    try:
        token_payload = decode_token(payload.refresh_token)
        if token_payload.get("type") != "refresh":
            raise HTTPException(status_code=400, detail="Invalid token type")
        
        user_id = token_payload.get("sub")
        user = await get_user_by_id(db, user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User inactive or deleted")

        access_token, new_refresh_token = auth_service.generate_tokens(user)
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=3600
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get the currently authenticated user.
    """
    return current_user


@router.post("/logout")
async def logout():
    """
    Invalidates the current session. (Client-side token discard)
    """
    return {"message": "Successfully logged out"}
