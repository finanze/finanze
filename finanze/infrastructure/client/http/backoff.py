import logging
import random
import time
from typing import Any, Iterable, Optional, Callable

import requests
from requests import Response

DEFAULT_RETRIED_STATUSES: tuple[int, ...] = (429, 408)


def http_get_with_backoff(
    url: str,
    params: Optional[dict[str, Any]] = None,
    timeout: int = 10,
    *,
    max_retries: int = 3,
    backoff_exponent_base: float = 2.0,
    backoff_factor: float = 0.5,
    retried_statuses: Iterable[int] = DEFAULT_RETRIED_STATUSES,
    cooldown: Optional[float] = None,
    log: Optional[logging.Logger] = None,
    headers: Optional[dict[str, str]] = None,
    should_retry: Optional[Callable[[Response, int], bool]] = None,
) -> Response:
    attempt = 0
    status_retry_set = set(retried_statuses)
    last_exc: Exception | None = None

    while attempt <= max_retries:
        if cooldown:
            time.sleep(cooldown)
        try:
            resp = requests.get(url, params=params, timeout=timeout, headers=headers)
        except requests.RequestException as e:
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
                kind = "Timeout" if isinstance(e, requests.Timeout) else "ReqError"
                log.info(
                    f"Transient {kind} on {url} (attempt {attempt + 1}/{max_retries + 1}), backing off {delay:.2f}s"
                )
            time.sleep(delay)
            attempt += 1
            continue

        if (resp.status_code in status_retry_set) and not resp.ok:
            if attempt == max_retries:
                return resp
            delay = backoff_factor * (backoff_exponent_base**attempt) + random.uniform(
                0, backoff_factor
            )
            if log:
                log.info(
                    f"HTTP {resp.status_code} for {url} (attempt {attempt + 1}/{max_retries + 1}), retrying in {delay:.2f}s"
                )
            time.sleep(delay)
            attempt += 1
            continue

        if should_retry and should_retry(resp, attempt) and attempt < max_retries:
            delay = backoff_factor * (backoff_exponent_base**attempt) + random.uniform(
                0, backoff_factor
            )
            if log:
                log.info(
                    f"Predicate retry for {url} (attempt {attempt + 1}/{max_retries + 1}) in {delay:.2f}s"
                )
            time.sleep(delay)
            attempt += 1
            continue

        return resp

    if last_exc:
        raise last_exc
    raise RuntimeError("http_get_with_backoff reached an unexpected state")
