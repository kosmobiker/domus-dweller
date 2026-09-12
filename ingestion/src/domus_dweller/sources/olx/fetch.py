from __future__ import annotations

import time

from curl_cffi import requests as curl_requests


def fetch_search_page(
    url: str,
    *,
    timeout: int = 45,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    impersonate: str = "chrome",
) -> str:
    """Fetch search page HTML using curl_cffi with browser TLS impersonation."""
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response = curl_requests.get(
                url,
                impersonate=impersonate,
                timeout=timeout,
            )
            if response.status_code == 200:
                return response.text

            msg = (
                f"Failed to fetch {url}: HTTP {response.status_code} "
                f"on attempt {attempt}/{max_retries}"
            )
            last_error = RuntimeError(msg)
        except Exception as exc:  # noqa: BLE001
            last_error = RuntimeError(
                f"Network error fetching {url} on attempt {attempt}/{max_retries}: {exc}"
            )

        if attempt < max_retries:
            time.sleep(retry_delay * attempt)

    if last_error:
        raise last_error
    raise RuntimeError(f"Failed to fetch {url} after {max_retries} attempts")
