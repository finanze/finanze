import logging
from typing import Any, Callable

import requests
from cachetools import TTLCache, cached
from domain.crypto import CryptoAsset
from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.exception.exceptions import (
    FeatureNotSupported,
    InvalidProvidedCredentials,
    MissingFieldsError,
    TooManyRequests,
)
from domain.native_entities import BSC, ETHEREUM, TRON
from infrastructure.client.http.backoff import http_get_with_backoff


class CoinGeckoClient:
    BASE_URL = "https://api.coingecko.com/api/v3"
    TIMEOUT = 10
    CHUNK_SIZE = 50
    COOLDOWN = 1
    MAX_RETRIES = 4
    BACKOFF_EXPONENT_BASE = 2.8
    BACKOFF_FACTOR = 1.6

    ENTITY_CHAIN_MAP = {
        ETHEREUM: "ethereum",
        BSC: "binance-smart-chain",
        TRON: "tron",
    }

    def __init__(self):
        self._log = logging.getLogger(__name__)

    def search(self, query: str) -> list[CryptoAsset]:
        if not query or not query.strip():
            raise MissingFieldsError(["query"])
        data = self._fetch("/search", params={"query": query.strip()})
        coins = data.get("coins", [])
        return self._map_search_results(coins)

    @cached(
        cache=TTLCache(maxsize=1, ttl=86400),
    )
    def get_coin_list(self) -> list[dict[str, Any]]:
        params = {"include_platform": "true"}
        data = self._fetch("/coins/list", params=params, timeout=self.TIMEOUT)
        if not isinstance(data, list):
            self._log.warning(
                f"Unexpected response for /coins/list, expected list. Got type {type(data)}"
            )
            return []

        return data

    def get_prices_by_contract(
        self,
        crypto_entity: Entity,
        addresses: list[str],
        vs_currencies: list[str],
        timeout: int = TIMEOUT,
    ) -> dict[str, dict[str, Dezimal]]:
        chain_slug = self.ENTITY_CHAIN_MAP.get(crypto_entity)
        if not chain_slug:
            raise FeatureNotSupported(
                f"Token prices not supported for chain {getattr(crypto_entity, 'name', 'UNKNOWN')}"
            )
        deduped_addresses = self._dedupe_items(addresses, case_insensitive=False)
        vs_param = ",".join(c.lower() for c in vs_currencies)
        result: dict[str, dict[str, Dezimal]] = {}
        for chunk in self._chunked(deduped_addresses, self.CHUNK_SIZE):
            chunk_result = self._fetch_token_chunk(chain_slug, chunk, vs_param, timeout)
            self._merge_prices_map(
                chunk_result, result, key_transform=lambda k: k.lower()
            )
        return result

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
        deduped = self._dedupe_items(symbols, case_insensitive=True)
        vs_param = ",".join(c.lower() for c in vs_currencies)
        return deduped, vs_param

    def _aggregate_prices(
        self, deduped: list[str], vs_param: str, timeout: int
    ) -> dict[str, dict[str, Dezimal]]:
        result: dict[str, dict[str, Dezimal]] = {}
        for chunk in self._chunked(deduped, self.CHUNK_SIZE):
            chunk_result = self._fetch_chunk(chunk, vs_param, timeout)
            self._merge_prices_map(
                chunk_result, result, key_transform=lambda k: k.upper()
            )
        return result

    def _chunked(self, seq: list[str], size: int) -> list[list[str]]:
        return [seq[i : i + size] for i in range(0, len(seq), size)]

    def _merge_prices_map(
        self,
        raw_map: dict[str, Any],
        accumulator: dict[str, dict[str, Dezimal]],
        key_transform: Callable[[str], str],
    ) -> None:
        for key, prices in raw_map.items():
            converted = self._convert_prices(prices)
            if converted:
                accumulator[key_transform(key)] = converted

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

    def _dedupe_items(self, items: list[str], case_insensitive: bool) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for raw in items:
            item = raw.strip()
            if not item:
                continue
            key = item.lower() if case_insensitive else item
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
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

    # --- Token (contract) prices helpers ---
    def _fetch_token_chunk(
        self, chain_slug: str, chunk: list[str], vs_param: str, timeout: int
    ) -> dict[str, Any]:
        addresses_param = ",".join(chunk)
        path = f"/simple/token_price/{chain_slug}"
        return self._fetch(
            path,
            params={
                "vs_currencies": vs_param,
                "contract_addresses": addresses_param,
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
                backoff_exponent_base=self.BACKOFF_EXPONENT_BASE,
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
