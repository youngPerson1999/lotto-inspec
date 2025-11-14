"""Thin HTTP client helpers built on top of requests."""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests
from requests import Response

from app.core.config import get_settings


def fetch_url(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = None,
) -> Response:
    """Fetch a URL with a shared user agent and timeout defaults."""

    settings = get_settings()
    session_headers = {
        "User-Agent": settings.user_agent,
        **(headers or {}),
    }

    response = requests.get(
        url,
        params=params,
        headers=session_headers,
        timeout=timeout or settings.request_timeout,
    )
    response.raise_for_status()
    return response


def fetch_text(url: str, **kwargs: Any) -> str:
    """Convenience wrapper returning decoded text."""

    response = fetch_url(url, **kwargs)
    return response.text

