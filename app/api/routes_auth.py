"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas import (
    MessageResponse,
    TokenPairResponse,
    UserLoginRequest,
    UserProfileResponse,
    UserRegisterRequest,
    RefreshTokenRequest,
)
from app.services.auth import (
    authenticate_user,
    create_user,
    get_current_user,
    issue_tokens_for_user,
    oauth2_scheme,
    remove_refresh_token,
    user_profile,
    validate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserProfileResponse,
    summary="신규 사용자 등록",
)
def register_user(payload: UserRegisterRequest) -> UserProfileResponse:
    user = create_user(
        user_id=payload.userId,
        password=payload.password,
        name=payload.name,
    )
    return UserProfileResponse(**user)


@router.post(
    "/login",
    response_model=TokenPairResponse,
    summary="로그인 및 토큰 발급",
)
def login(payload: UserLoginRequest) -> TokenPairResponse:
    user = authenticate_user(payload.userId, payload.password)
    tokens = issue_tokens_for_user(user)
    return TokenPairResponse(**tokens)


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    summary="리프레시 토큰으로 토큰 재발급",
)
def refresh_tokens(payload: RefreshTokenRequest) -> TokenPairResponse:
    user = validate_refresh_token(payload.refresh_token)
    remove_refresh_token(payload.refresh_token)
    tokens = issue_tokens_for_user(user)
    return TokenPairResponse(**tokens)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="리프레시 토큰 폐기",
)
def logout(payload: RefreshTokenRequest) -> MessageResponse:
    validate_refresh_token(payload.refresh_token)
    remove_refresh_token(payload.refresh_token)
    return MessageResponse(message="로그아웃 완료")


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="현재 사용자 정보",
)
def get_me(
    credentials=Depends(oauth2_scheme),
) -> UserProfileResponse:
    user = get_current_user(credentials)
    return UserProfileResponse(**user_profile(user))


__all__ = ["router"]
