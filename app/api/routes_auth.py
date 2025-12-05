"""Authentication endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.dto import (
    EmailVerificationRequest,
    MessageResponse,
    ResendVerificationRequest,
    TokenPairResponse,
    UserLoginRequest,
    UserProfileResponse,
    UserRegisterRequest,
    RefreshTokenRequest,
)
from app.services.auth import (
    authenticate_user,
    create_user,
    create_email_verification_token,
    EmailVerificationError,
    get_current_user,
    issue_tokens_for_user,
    oauth2_scheme,
    remove_refresh_token,
    resend_verification_token,
    verify_email_token,
    user_profile,
    validate_refresh_token,
)
from app.services.email import send_verification_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserProfileResponse,
    summary="신규 사용자 등록",
)
async def register_user(payload: UserRegisterRequest) -> UserProfileResponse:
    user = create_user(
        user_id=payload.userId,
        password=payload.password,
        name=payload.name,
    )
    user_pk = user.get("id")
    if user_pk is not None:
        token = create_email_verification_token(int(user_pk))
        try:
            await send_verification_email(user["userId"], token)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to send verification email to %s", user["userId"])
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


@router.post(
    "/verify-email",
    response_model=MessageResponse,
    summary="이메일 인증 완료 처리",
)
def verify_email(payload: EmailVerificationRequest) -> MessageResponse:
    try:
        verify_email_token(payload.token)
    except EmailVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(exc)},
        ) from exc
    return MessageResponse(message="Email verification successful.")


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="이메일 인증 메일 재발송",
)
async def resend_verification(payload: ResendVerificationRequest) -> MessageResponse:
    exists, already_verified, token = resend_verification_token(payload.userId)

    if not exists:
        return MessageResponse(
            message="If the account exists, a verification email was sent."
        )
    if already_verified:
        return MessageResponse(message="User already verified.")

    if token:
        try:
            await send_verification_email(payload.userId, token)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to resend verification email to %s", payload.userId)
    return MessageResponse(message="Verification email re-sent. Please check your inbox.")


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
