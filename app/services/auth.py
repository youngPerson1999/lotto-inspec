"""Authentication and JWT helper utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.db import session_scope
from app.core.models import RefreshTokenORM, UserORM

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = HTTPBearer(auto_error=False)


def _ensure_database_backend() -> None:
    if not get_settings().use_database_storage:
        raise RuntimeError("MariaDB 백엔드에서만 인증 기능을 사용할 수 있습니다.")


def _user_to_dict(record: UserORM) -> Dict[str, Any]:
    return {
        "id": record.id,
        "user_id": record.user_id,
        "password_hash": record.password_hash,
        "name": record.name,
        "created_at": record.created_at,
    }


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _token_payload(user_id: str) -> Dict[str, Any]:
    return {"sub": user_id}


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_exp_minutes
    )
    payload = {
        **_token_payload(user_id),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> Dict[str, Any]:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_exp_days
    )
    payload = {
        **_token_payload(user_id),
        "exp": expire,
        "type": "refresh",
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"token": token, "expires_at": expire}


def decode_token(token: str, expected_type: str = "access") -> Dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 만료되었습니다.",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
        ) from exc

    if payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰 타입이 올바르지 않습니다.",
        )
    return payload


def _serialize_user(document: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": document.get("id"),
        "userId": document["user_id"],
        "name": document["name"],
    }


def user_profile(document: Dict[str, Any]) -> Dict[str, Any]:
    return _serialize_user(document)


def create_user(user_id: str, password: str, name: str) -> Dict[str, Any]:
    _ensure_database_backend()
    with session_scope() as session:
        existing = session.scalars(
            select(UserORM).where(UserORM.user_id == user_id)
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 존재하는 사용자 ID입니다.",
            )

        record = UserORM(
            user_id=user_id,
            password_hash=hash_password(password),
            name=name,
            created_at=datetime.now(timezone.utc),
        )
        session.add(record)
        session.flush()
        document = _user_to_dict(record)
    return _serialize_user(document)


def authenticate_user(user_id: str, password: str) -> Dict[str, Any]:
    _ensure_database_backend()
    with session_scope() as session:
        record = session.scalars(
            select(UserORM).where(UserORM.user_id == user_id)
        ).first()

    if not record or not verify_password(password, record.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자 ID 또는 비밀번호가 올바르지 않습니다.",
        )
    return _user_to_dict(record)


def store_refresh_token(user_id: str, token: str, expires_at: datetime) -> None:
    _ensure_database_backend()
    with session_scope() as session:
        session.add(
            RefreshTokenORM(
                user_id=user_id,
                token=token,
                expires_at=expires_at,
                created_at=datetime.now(timezone.utc),
            )
        )


def remove_refresh_token(token: str) -> None:
    _ensure_database_backend()
    with session_scope() as session:
        session.execute(
            delete(RefreshTokenORM).where(RefreshTokenORM.token == token)
        )


def find_user_by_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    _ensure_database_backend()
    with session_scope() as session:
        row = session.execute(
            select(UserORM, RefreshTokenORM)
            .join(
                RefreshTokenORM,
                RefreshTokenORM.user_id == UserORM.user_id,
            )
            .where(RefreshTokenORM.token == token)
        ).first()

    if not row:
        return None

    user, refresh = row
    document = _user_to_dict(user)
    document["refresh_tokens"] = [
        {"token": refresh.token, "expires_at": refresh.expires_at}
    ]
    return document


def revoke_all_refresh_tokens(user_id: str) -> None:
    _ensure_database_backend()
    with session_scope() as session:
        session.execute(
            delete(RefreshTokenORM).where(RefreshTokenORM.user_id == user_id)
        )


def issue_tokens_for_user(user: Dict[str, Any]) -> Dict[str, Any]:
    access_token = create_access_token(user["user_id"])
    refresh = create_refresh_token(user["user_id"])
    store_refresh_token(user["user_id"], refresh["token"], refresh["expires_at"])

    return {
        "access_token": access_token,
        "refresh_token": refresh["token"],
        "token_type": "Bearer",
        "expires_in": get_settings().jwt_access_token_exp_minutes * 60,
        "refresh_expires_in": get_settings().jwt_refresh_token_exp_days * 24 * 3600,
        "user": _serialize_user(user),
    }


def get_current_user(credentials: HTTPAuthorizationCredentials | None) -> Dict[str, Any]:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 정보가 제공되지 않았습니다.",
        )

    payload = decode_token(credentials.credentials, expected_type="access")
    user_id = payload["sub"]
    _ensure_database_backend()
    with session_scope() as session:
        record = session.scalars(
            select(UserORM).where(UserORM.user_id == user_id)
        ).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없습니다.",
        )
    return _user_to_dict(record)


def require_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(oauth2_scheme),
) -> Dict[str, Any]:
    """FastAPI dependency that ensures the presence of a valid access token."""

    return get_current_user(credentials)


def validate_refresh_token(token: str) -> Dict[str, Any]:
    payload = decode_token(token, expected_type="refresh")
    user = find_user_by_refresh_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="등록되지 않은 리프레시 토큰입니다.",
        )

    match = next(
        (
            entry
            for entry in user.get("refresh_tokens", [])
            if entry.get("token") == token
        ),
        None,
    )
    if not match:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="등록되지 않은 리프레시 토큰입니다.",
        )

    expires_at = match.get("expires_at")
    if isinstance(expires_at, datetime) and expires_at < datetime.now(timezone.utc):
        remove_refresh_token(token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="리프레시 토큰이 만료되었습니다.",
        )

    return user


__all__ = [
    "create_user",
    "authenticate_user",
    "issue_tokens_for_user",
    "find_user_by_refresh_token",
    "remove_refresh_token",
    "decode_token",
    "get_current_user",
    "validate_refresh_token",
    "user_profile",
    "oauth2_scheme",
    "require_access_token",
]
