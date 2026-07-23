"""Authentication endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...core.security import create_access_token, verify_password
from ...models import User
from ...schemas import LoginRequest, Token, UserOut, user_out
from ..deps import get_current_user

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=Token)
async def login(payload: LoginRequest):
    user = await User.find_one(User.username == payload.username)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = create_access_token(subject=user.username, role=user.role.value)
    return Token(
        access_token=token,
        role=user.role,
        username=user.username,
        full_name=user.full_name,
    )


@router.get("/auth/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user_out(user)
