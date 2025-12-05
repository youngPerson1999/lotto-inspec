"""Asynchronous helpers for sending transactional emails."""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _build_verification_email(to_email: str, token: str) -> EmailMessage:
    settings = get_settings()
    frontend = settings.frontend_host.rstrip("/")
    verification_url = f"{frontend}/auth/verify?token={token}"
    subject = "Verify your Lotto Insec account"

    body = (
        "안녕하세요!\n\n"
        "Lotto Insec 계정을 활성화하려면 아래 링크를 눌러 이메일을 인증해주세요:\n\n"
        f"{verification_url}\n\n"
        "이 링크는 1시간 후 만료됩니다. 만약 본인이 요청하지 않았다면 이 메일을 무시하세요.\n\n"
        "감사합니다."
    )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.email_from
    message["To"] = to_email
    message.set_content(body)
    return message


def _send_email(message: EmailMessage) -> None:
    settings = get_settings()
    if not settings.email_host:
        logger.warning("EMAIL_HOST is not configured; skipping email send.")
        return

    with smtplib.SMTP(
        host=settings.email_host,
        port=settings.email_port,
        timeout=settings.email_timeout,
    ) as server:
        if settings.email_use_tls:
            server.starttls()
        if settings.email_user:
            server.login(settings.email_user, settings.email_password)
        server.send_message(message)


async def send_verification_email(to_email: str, token: str) -> None:
    """Send an email verification link to the provided address."""

    settings = get_settings()
    if not settings.email_from or not to_email:
        logger.warning("Email sender or recipient missing; skipping verification email.")
        return

    message = _build_verification_email(to_email, token)
    try:
        await asyncio.to_thread(_send_email, message)
        logger.info("Verification email dispatched to %s", to_email)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send verification email to %s", to_email)


__all__ = ["send_verification_email"]
