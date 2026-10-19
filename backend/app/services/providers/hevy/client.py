"""HTTP client for the Hevy public API.

Auth is a per-account API key in the ``api-key`` header. Pages are numbered and
capped at 10 items. There is no OAuth client and no webhook.
"""

from collections.abc import Iterator
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.config import settings

API_BASE_URL = "https://api.hevyapp.com"
PAGE_SIZE = 10


class HevyRejectedKeyError(Exception):
    """Hevy answered 401 for this API key."""


def request_json(api_key: str, path: str, params: dict[str, Any] | None = None) -> Any:
    """GET one Hevy resource. Raises HevyRejectedKeyError on 401 and HTTPException otherwise."""
    url = f"{API_BASE_URL}{path}"
    try:
        with httpx.Client() as client:
            response = client.get(
                url,
                headers={"api-key": api_key, "Accept": "application/json"},
                params=params or {},
                timeout=settings.provider_request_timeout_seconds,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach Hevy.",
        ) from exc

    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        raise HevyRejectedKeyError()

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Hevy returned an error.",
        ) from exc

    return response.json()


def fetch_profile(api_key: str) -> dict[str, Any]:
    """The account that owns this key. Used to confirm the key before storing it."""
    payload = request_json(api_key, "/v1/user/info")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Hevy returned an unexpected profile.")
    return payload


def iter_collection(api_key: str, path: str, collection_key: str) -> Iterator[dict[str, Any]]:
    """Walk a page/pageSize collection until Hevy reports the last page."""
    page = 1
    while True:
        payload = request_json(api_key, path, {"page": page, "pageSize": PAGE_SIZE})
        if not isinstance(payload, dict):
            return
        items = payload.get(collection_key) or []
        if not isinstance(items, list):
            return
        for item in items:
            if isinstance(item, dict):
                yield item
        page_count = payload.get("page_count") or 1
        try:
            last_page = int(page_count)
        except (TypeError, ValueError):
            return
        if page >= last_page or len(items) < PAGE_SIZE:
            return
        page += 1
