import asyncio
import logging
import random
from typing import Any, Iterable, Optional, Callable, Awaitable

import httpx

from infrastructure.client.http.http_session import get_http_session
from infrastructure.client.http.http_response import HttpResponse

DEFAULT_RETRIED_STATUSES: tuple[int, ...] = (429, 408)


async def http_get_with_backoff(
    url: str,
    params: Optional[dict[str, Any]] = None,
    request_timeout: int = 10,
    *,
    max_retries: int = 3,
    backoff_exponent_base: float = 2.0,
    backoff_factor: float = 0.5,
    retried_statuses: Iterable[int] = DEFAULT_RETRIED_STATUSES,
    cooldown: Optional[float] = None,
    log: Optional[logging.Logger] = None,
    headers: Optional[dict[str, str]] = None,
    should_retry: Optional[
        Callable[[HttpResponse, int], bool | Awaitable[bool]]
    ] = None,
) -> HttpResponse:
    attempt = 0
    status_retry_set = set(retried_statuses)
    last_exc: Exception | None = None

    session = get_http_session()

    while attempt <= max_retries:
        if cooldown:
            await asyncio.sleep(cooldown)

        try:
            resp = await session.get(
                url, params=params, timeout=request_timeout, headers=headers
            )
        except (httpx.RequestError, TimeoutError) as e:
            last_exc = e
            if attempt == max_retries:
                if log:
                    log.warning(
                        f"HTTP GET {url} failed on attempt {attempt + 1}/{max_retries + 1}: {e}"
                    )
                raise

            delay = backoff_factor * (backoff_exponent_base**attempt) + random.uniform(
                0, backoff_factor
            )
            if log:
                kind = "Timeout" if isinstance(e, TimeoutError) else "ReqError"
                log.info(
                    f"Transient {kind} on {url} (attempt {attempt + 1}/{max_retries + 1}), backing off {delay:.2f}s"
                )
            await asyncio.sleep(delay)
            attempt += 1
            continue

        if (resp.status in status_retry_set) and not (200 <= resp.status < 300):
            if attempt == max_retries:
                return resp

            await resp.release()
            delay = backoff_factor * (backoff_exponent_base**attempt) + random.uniform(
                0, backoff_factor
            )
            if log:
                log.info(
                    f"HTTP {resp.status} for {url} (attempt {attempt + 1}/{max_retries + 1}), retrying in {delay:.2f}s"
                )
            await asyncio.sleep(delay)
            attempt += 1
            continue

        if should_retry:
            decision = should_retry(resp, attempt)
            if isinstance(decision, Awaitable):
                decision = await decision
            if decision and attempt < max_retries:
                await resp.release()
                delay = backoff_factor * (
                    backoff_exponent_base**attempt
                ) + random.uniform(0, backoff_factor)
                if log:
                    log.info(
                        f"Predicate retry for {url} (attempt {attempt + 1}/{max_retries + 1}) in {delay:.2f}s"
                    )
                await asyncio.sleep(delay)
                attempt += 1
                continue

        return resp

    if last_exc:
        raise last_exc
    raise RuntimeError("http_get_with_backoff reached an unexpected state")
