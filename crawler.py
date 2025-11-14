"""Simple web crawling helper built on top of the requests package."""

from typing import Any, Dict, Optional

import requests
from requests import Response


def fetch_url(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 10.0,
) -> Response:
    """Fetch a URL using requests with basic resiliency helpers.

    Args:
        url: Absolute URL to crawl.
        params: Optional query parameters.
        headers: Optional HTTP headers (User-Agent etc.).
        timeout: Socket timeout in seconds.

    Returns:
        requests.Response object with the downloaded content.

    Raises:
        requests.HTTPError: If the response status is 4xx/5xx.
        requests.RequestException: For networking errors such as timeouts.
    """

    session_headers = {
        "User-Agent": "lotto-insec/1.0 (+https://example.com)",
        **(headers or {}),
    }

    response = requests.get(
        url,
        params=params,
        headers=session_headers,
        timeout=timeout,
    )
    response.raise_for_status()
    return response


def fetch_text(url: str, **kwargs: Any) -> str:
    """Convenience wrapper returning decoded text."""

    response = fetch_url(url, **kwargs)
    return response.text
