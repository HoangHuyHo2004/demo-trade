"""Shared HTTP helpers for provider adapters.

Uses an httpx.AsyncClient with:
  * sane timeouts
  * retry on transient failure
  * an allowlist check so a compromised config can't SSRF arbitrary hosts.
"""
from __future__ import annotations

import asyncio
from urllib.parse import urlparse

import httpx

from app.core.logging import get_logger

log = get_logger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)


def check_allowlisted(url: str, allowed_hosts: set[str]) -> None:
    host = urlparse(url).hostname or ""
    if host not in allowed_hosts:
        raise ValueError(
            f"HTTP call to host {host!r} not in allowlist "
            f"{sorted(allowed_hosts)}"
        )


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict | None = None,
    max_retries: int = 3,
    backoff: float = 0.5,
) -> object:
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            r = await client.get(url, params=params, timeout=DEFAULT_TIMEOUT)
            if r.status_code == 429 or 500 <= r.status_code < 600:
                raise httpx.HTTPStatusError(
                    "transient", request=r.request, response=r
                )
            r.raise_for_status()
            return r.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            last_exc = e
            log.warning("http_retry", url=url, attempt=attempt, err=str(e))
            await asyncio.sleep(backoff * (2**attempt))
    assert last_exc is not None
    raise last_exc
