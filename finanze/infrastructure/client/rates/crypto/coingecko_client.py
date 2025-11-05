import logging
from typing import Any

import requests
from domain.crypto import CryptoAsset
from domain.dezimal import Dezimal
from domain.exception.exceptions import (
    InvalidProvidedCredentials,
    MissingFieldsError,
    TooManyRequests,
)
from infrastructure.client.http.backoff import http_get_with_backoff


class CoinGeckoClient:
    BASE_URL = "https://api.coingecko.com/api/v3"
    TIMEOUT = 10
    CHUNK_SIZE = 50
    COOLDOWN = 1
    MAX_RETRIES = 3
    BACKOFF_FACTOR = 1.6

    def __init__(self):
        self._log = logging.getLogger(__name__)

    def search(self, query: str) -> list[CryptoAsset]:
        if not query or not query.strip():
            raise MissingFieldsError(["query"])
        data = self._fetch("/search", params={"query": query.strip()})
        coins = data.get("coins", [])
        return self._map_search_results(coins)

    def _map_search_results(self, coins: list[dict[str, Any]]) -> list[CryptoAsset]:
        mapped: list[CryptoAsset] = []
        for c in coins:
            try:
                ext_id = c.get("id")
                name = c.get("name")
                symbol = c.get("symbol")
                if not ext_id or not name or not symbol:
                    continue

                icon_urls = [c.get("large")]
                external_ids = {
                    "COINGECKO": ext_id,
                }
                mapped.append(
                    CryptoAsset(
                        name=name,
                        symbol=symbol,
                        icon_urls=icon_urls or [],
                        external_ids=external_ids,
                    )
                )
            except Exception as e:
                self._log.error(f"Failed to map coin {c}: {e}")
                continue
        return mapped

    def get_prices(  # noqa: C901
        self, symbols: list[str], vs_currencies: list[str], timeout: int = TIMEOUT
    ) -> dict[str, dict[str, Dezimal]]:
        return self._get_prices_impl(symbols, vs_currencies, timeout)

    def _get_prices_impl(
        self, symbols: list[str], vs_currencies: list[str], timeout: int
    ) -> dict[str, dict[str, Dezimal]]:
        deduped, vs_param = self._validate_and_prepare(symbols, vs_currencies)
        return self._aggregate_prices(deduped, vs_param, timeout)

    def _validate_and_prepare(
        self, symbols: list[str], vs_currencies: list[str]
    ) -> tuple[list[str], str]:
        if not symbols:
            raise MissingFieldsError(["symbols"])
        if not vs_currencies:
            raise MissingFieldsError(["vs_currencies"])
        deduped = self._dedupe(symbols)
        vs_param = ",".join(c.lower() for c in vs_currencies)
        return deduped, vs_param

    def _aggregate_prices(
        self, deduped: list[str], vs_param: str, timeout: int
    ) -> dict[str, dict[str, Dezimal]]:
        result: dict[str, dict[str, Dezimal]] = {}
        for chunk in self._chunked(deduped, self.CHUNK_SIZE):
            chunk_result = self._fetch_chunk(chunk, vs_param, timeout)
            self._merge_chunk(chunk_result, result)
        return result

    def _chunked(self, seq: list[str], size: int) -> list[list[str]]:
        return [seq[i : i + size] for i in range(0, len(seq), size)]

    def _merge_chunk(
        self, chunk_result: dict[str, Any], accumulator: dict[str, dict[str, Dezimal]]
    ) -> None:
        for sym, prices in chunk_result.items():
            converted = self._convert_prices(prices)
            if converted:
                accumulator[sym.upper()] = converted

    def _convert_prices(self, prices: Any) -> dict[str, Dezimal]:
        if not isinstance(prices, dict):
            return {}
        converted: dict[str, Dezimal] = {}
        for cur, val in prices.items():
            try:
                converted[cur.upper()] = Dezimal(val)
            except Exception:
                continue
        return converted

    def _dedupe(self, symbols: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for s in symbols:
            su = s.strip()
            if not su:
                continue
            lu = su.lower()
            if lu in seen:
                continue
            seen.add(lu)
            deduped.append(su)
        return deduped

    def _fetch_chunk(
        self, chunk: list[str], vs_param: str, timeout: int
    ) -> dict[str, Any]:
        symbols_param = ",".join(s.lower() for s in chunk)
        return self._fetch(
            "/simple/price",
            params={
                "vs_currencies": vs_param,
                "symbols": symbols_param,
                "precision": "full",
            },
            timeout=timeout,
        )

    def _fetch(
        self, path: str, params: dict[str, Any] | None = None, timeout: int = TIMEOUT
    ) -> dict:
        url = f"{self.BASE_URL}{path}"
        try:
            response = http_get_with_backoff(
                url,
                params=params,
                timeout=timeout,
                max_retries=self.MAX_RETRIES,
                backoff_exponent_base=3,
                backoff_factor=self.BACKOFF_FACTOR,
                cooldown=self.COOLDOWN,
                log=self._log,
            )
        except requests.Timeout as e:
            self._log.warning(f"Timeout calling CoinGecko endpoint {url}")
            raise e
        except requests.RequestException as e:
            self._log.error(f"Request error calling CoinGecko endpoint {url}: {e}")
            raise e

        if not response.ok:
            status = response.status_code
            body = response.text
            if status == 429:
                raise TooManyRequests()
            if status in (401, 403):
                raise InvalidProvidedCredentials()
            if status == 400:
                self._log.error(f"Bad request to CoinGecko {url}: {body}")
                raise ValueError("Invalid request to CoinGecko API")
            if status in (500, 503):
                self._log.error(f"CoinGecko service error {status}: {body}")
                response.raise_for_status()
            if status == 408:
                self._log.warning(f"CoinGecko timeout status for {url}: {body}")
                response.raise_for_status()
            self._log.error(f"Unexpected CoinGecko response {status} for {url}: {body}")
            response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            self._log.error(
                f"Failed to decode JSON from CoinGecko for {url}: {response.text[:200]}"
            )
            raise
