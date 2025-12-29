import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

import requests
from cachetools import TTLCache, cached
from dateutil.tz import tzlocal

from domain.crypto import (
    AvailableCryptoAsset,
    CryptoAsset,
    CryptoAssetDetails,
    CryptoAssetPlatform,
    CryptoPlatform,
    CryptoCurrencyType,
)
from domain.dezimal import Dezimal
from domain.entity import Entity
from domain.exception.exceptions import (
    InvalidProvidedCredentials,
    MissingFieldsError,
    TooManyRequests,
)
from domain.external_integration import ExternalIntegrationId
from domain.native_entities import BSC, ETHEREUM, TRON, BITCOIN, LITECOIN
from infrastructure.client.http.backoff import http_get_with_backoff


class CoinGeckoClient:
    BASE_URL = "https://api.coingecko.com/api/v3"
    TIMEOUT = 10
    CHUNK_SIZE = 50
    COOLDOWN = 1
    MAX_RETRIES = 4
    BACKOFF_EXPONENT_BASE = 2.8
    BACKOFF_FACTOR = 1.6
    CACHE_FILENAME = "coingecko.json"
    CACHE_MAX_AGE_DAYS = 4

    ENTITY_CHAIN_MAP = {
        "bitcoin": BITCOIN,
        "ethereum": ETHEREUM,
        "binance-smart-chain": BSC,
        "tron": TRON,
        "litecoin": LITECOIN,
    }

    def __init__(self, app_dir: str):
        self._log = logging.getLogger(__name__)
        self._cache_file_path: str | None = None
        self._coin_list_cache: list[dict[str, Any]] | None = None
        self._coin_list_last_updated: datetime | None = None
        self._platforms_cache: list[dict[str, Any]] | None = None
        self._platforms_last_updated: datetime | None = None

        self._cache_file_path = os.path.join(app_dir, self.CACHE_FILENAME)
        self._load_coin_list_cache()
        self._load_platforms_cache()

    def search(self, query: str) -> list[CryptoAsset]:
        if not query or not query.strip():
            raise MissingFieldsError(["query"])
        data = self._fetch("/search", params={"query": query.strip()})
        coins = data.get("coins", [])
        return self._map_search_results(coins)

    def _map_search_results(self, coins: list[dict[str, Any]]) -> list[CryptoAsset]:
        results: list[CryptoAsset] = []
        for coin in coins:
            if not isinstance(coin, dict):
                continue
            try:
                coin_id = coin.get("id")
                if not coin_id:
                    continue
                name = coin.get("name") or ""
                symbol = coin.get("symbol")
                if symbol:
                    symbol = symbol.upper()
                icon_urls: list[str] = []
                thumb = coin.get("thumb")
                large = coin.get("large")
                if large:
                    icon_urls.append(large)
                if not large and thumb:
                    icon_urls.append(thumb)
                external_ids = {ExternalIntegrationId.COINGECKO.value: coin_id}
                results.append(
                    CryptoAsset(
                        name=name,
                        symbol=symbol,
                        icon_urls=icon_urls if icon_urls else None,
                        external_ids=external_ids,
                    )
                )
            except Exception as e:
                self._log.warning(f"Failed to map search result for coin: {e}")
                continue
        return results

    def _load_coin_list_cache(self) -> None:
        if not self._cache_file_path or not os.path.exists(self._cache_file_path):
            return

        try:
            if os.path.getsize(self._cache_file_path) == 0:
                return

            with open(self._cache_file_path, "r") as f:
                data: dict[str, Any] = json.load(f)

            if not isinstance(data, dict):
                return

            coins_data = data.get("coins", {})
            if not isinstance(coins_data, dict):
                return

            last_updated_raw = coins_data.get("last_updated")
            if isinstance(last_updated_raw, str):
                try:
                    self._coin_list_last_updated = datetime.fromisoformat(
                        last_updated_raw
                    )
                except Exception:
                    self._log.warning(
                        "Malformed last_updated timestamp in coingecko.json"
                    )

            result = coins_data.get("result")
            if isinstance(result, list):
                self._coin_list_cache = result

        except Exception as e:
            self._log.warning(f"Failed to load coin list from cache: {e}")

    def _load_platforms_cache(self) -> None:
        if not self._cache_file_path or not os.path.exists(self._cache_file_path):
            return

        try:
            if os.path.getsize(self._cache_file_path) == 0:
                return

            with open(self._cache_file_path, "r") as f:
                data: dict[str, Any] = json.load(f)

            if not isinstance(data, dict):
                return

            platforms_data = data.get("platforms", {})
            if not isinstance(platforms_data, dict):
                return

            last_updated_raw = platforms_data.get("last_updated")
            if isinstance(last_updated_raw, str):
                try:
                    self._platforms_last_updated = datetime.fromisoformat(
                        last_updated_raw
                    )
                except Exception:
                    self._log.warning(
                        "Malformed last_updated timestamp for platforms in coingecko.json"
                    )

            result = platforms_data.get("result")
            if isinstance(result, list):
                self._platforms_cache = result

        except Exception as e:
            self._log.warning(f"Failed to load platforms from cache: {e}")

    def _save_coin_list_cache(self, coin_list: list[dict[str, Any]]) -> None:
        if not self._cache_file_path:
            return

        try:
            self._coin_list_last_updated = datetime.now(tzlocal())

            existing_data = self._read_cache_file()
            existing_data["coins"] = {
                "last_updated": self._coin_list_last_updated.isoformat(),
                "result": coin_list,
            }

            with open(self._cache_file_path, "w") as f:
                json.dump(existing_data, f, indent=2)

            self._coin_list_cache = coin_list

        except Exception as e:
            self._log.exception(f"Failed to persist coin list cache: {e}")

    def _read_cache_file(self) -> dict[str, Any]:
        if not self._cache_file_path or not os.path.exists(self._cache_file_path):
            return {}
        try:
            if os.path.getsize(self._cache_file_path) == 0:
                return {}
            with open(self._cache_file_path, "r") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_platforms_cache(self, platforms: list[dict[str, Any]]) -> None:
        if not self._cache_file_path:
            return

        try:
            self._platforms_last_updated = datetime.now(tzlocal())

            existing_data = self._read_cache_file()
            existing_data["platforms"] = {
                "last_updated": self._platforms_last_updated.isoformat(),
                "result": platforms,
            }

            with open(self._cache_file_path, "w") as f:
                json.dump(existing_data, f, indent=2)

            self._platforms_cache = platforms

        except Exception as e:
            self._log.exception(f"Failed to persist platforms cache: {e}")

    def _is_platforms_cache_valid(self) -> bool:
        if not self._platforms_cache or not self._platforms_last_updated:
            return False

        age = datetime.now(tzlocal()) - self._platforms_last_updated
        return age < timedelta(days=self.CACHE_MAX_AGE_DAYS)

    def _is_coin_list_cache_valid(self) -> bool:
        if not self._coin_list_cache or not self._coin_list_last_updated:
            return False

        age = datetime.now(tzlocal()) - self._coin_list_last_updated
        return age < timedelta(days=self.CACHE_MAX_AGE_DAYS)

    @cached(cache=TTLCache(maxsize=1, ttl=86400))
    def _get_coin_list(self) -> list[dict[str, Any]]:
        if self._is_coin_list_cache_valid():
            return self._coin_list_cache

        params = {"include_platform": "true"}
        try:
            data = self._fetch("/coins/list", params=params, timeout=self.TIMEOUT)
        except Exception as e:
            self._log.error(f"Failed to fetch coin list from CoinGecko: {e}")
            if self._coin_list_cache:
                self._log.warning("Returning stale cached coin list due to API error")
                return self._coin_list_cache
            return []

        if not isinstance(data, list):
            self._log.warning(
                f"Unexpected response for /coins/list, expected list. Got type {type(data)}"
            )

            if self._coin_list_cache:
                self._log.warning("Returning stale cached coin list due to API error")
                return self._coin_list_cache
            return []

        self._save_coin_list_cache(data)

        return data

    def asset_lookup(
        self, symbol: str | None = None, name: str | None = None
    ) -> list[AvailableCryptoAsset]:
        if not symbol and not name:
            return []

        query_lower = (symbol or name or "").strip().lower()
        if not query_lower:
            return []

        coin_list = self._get_coin_list()
        platforms_index = self.get_asset_platforms()
        matches: list[AvailableCryptoAsset] = []

        for coin in coin_list:
            if symbol:
                coin_symbol = (coin.get("symbol") or "").lower()
                if coin_symbol.startswith(query_lower):
                    asset = self._map_coin_to_available_asset(coin, platforms_index)
                    matches.append(asset)
            elif name:
                coin_name = (coin.get("name") or "").lower()
                if coin_name.startswith(query_lower):
                    asset = self._map_coin_to_available_asset(coin, platforms_index)
                    matches.append(asset)

        return matches

    def _map_coin_to_available_asset(
        self, coin: dict[str, Any], platforms_index: dict[str, CryptoPlatform]
    ) -> AvailableCryptoAsset:
        coin_platforms = coin.get("platforms") or {}
        enriched_platforms: list[CryptoAssetPlatform] = []

        for platform_id, contract_address in coin_platforms.items():
            if not platform_id or not contract_address:
                continue

            platform_info = platforms_index.get(platform_id)
            platform_name = platform_info.name if platform_info else platform_id
            icon_url = platform_info.icon_url if platform_info else None

            enriched_platforms.append(
                CryptoAssetPlatform(
                    provider_id=platform_id,
                    name=platform_name,
                    contract_address=contract_address,
                    icon_url=icon_url,
                    related_entity_id=None,
                )
            )

        return AvailableCryptoAsset(
            name=coin.get("name", ""),
            symbol=(coin.get("symbol") or "").upper(),
            platforms=enriched_platforms,
            provider=ExternalIntegrationId.COINGECKO,
            provider_id=coin.get("id", ""),
        )

    @cached(cache=TTLCache(maxsize=1, ttl=86400))
    def get_asset_platforms(self) -> dict[str, CryptoPlatform]:
        if self._is_platforms_cache_valid():
            return self._build_platforms_index(self._platforms_cache)

        try:
            data = self._fetch("/asset_platforms", timeout=self.TIMEOUT)
        except Exception as e:
            self._log.error(f"Failed to fetch asset platforms from CoinGecko: {e}")
            if self._platforms_cache:
                self._log.warning("Returning stale cached platforms due to API error")
                return self._build_platforms_index(self._platforms_cache)
            return {}

        if not isinstance(data, list):
            self._log.warning(
                f"Unexpected response for /asset_platforms, expected list. Got type {type(data)}"
            )

            if self._platforms_cache:
                self._log.warning("Returning stale cached platforms due to API error")
                return self._build_platforms_index(self._platforms_cache)
            return {}

        self._save_platforms_cache(data)

        return self._build_platforms_index(data)

    def _build_platforms_index(
        self, platforms: list[dict[str, Any]]
    ) -> dict[str, CryptoPlatform]:
        index: dict[str, CryptoPlatform] = {}
        for platform in platforms:
            platform_id = platform.get("id")
            if platform_id:
                image_info = platform.get("image") or {}
                icon_url = image_info.get("large") or image_info.get("small")
                index[platform_id] = CryptoPlatform(
                    provider_id=platform_id,
                    name=platform.get("name", platform_id),
                    icon_url=icon_url,
                )
        return index

    @cached(cache=TTLCache(maxsize=1, ttl=86400))
    def _get_coin_address_index(self) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        try:
            coin_list = self._get_coin_list()
        except Exception as e:
            self._log.error(f"Failed to fetch coin list for address overview: {e}")
            return index
        for coin in coin_list:
            self._add_platform_addresses(index, coin)
        return index

    def _add_platform_addresses(
        self, index: dict[str, dict[str, Any]], coin: dict[str, Any]
    ) -> None:
        try:
            coin_id = coin.get("id")
            if not coin_id:
                return
            platforms = coin.get("platforms") or {}
            if not isinstance(platforms, dict):
                return
            symbol = (coin.get("symbol") or "").upper() or None
            for _, addr in platforms.items():
                if not isinstance(addr, str):
                    continue
                normalized = addr.strip().lower()
                if not normalized or normalized in index:
                    continue
                index[normalized] = {
                    "id": coin_id,
                    "symbol": symbol,
                    "name": coin.get("name"),
                }
        except Exception:
            return

    def get_coin_overview_by_addresses(
        self, addresses: list[str]
    ) -> dict[str, dict[str, Any]]:
        if not addresses:
            return {}
        index = self._get_coin_address_index()
        result: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        for raw in addresses:
            if not isinstance(raw, str):
                continue
            addr = raw.strip().lower()
            if not addr or addr in seen:
                continue
            seen.add(addr)
            coin = index.get(addr)
            if coin:
                result[addr] = coin
        return result

    def get_prices_by_addresses(
        self,
        addresses: list[str],
        vs_currencies: list[str],
        timeout: int = TIMEOUT,
    ) -> dict[str, dict[str, Dezimal]]:
        if not addresses:
            return {}
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in addresses:
            if not isinstance(raw, str):
                continue
            addr = raw.strip().lower()
            if not addr or addr in seen:
                continue
            seen.add(addr)
            normalized.append(addr)
        if not normalized:
            return {}
        overview = self.get_coin_overview_by_addresses(normalized)
        id_to_addresses: dict[str, list[str]] = {}
        for addr in normalized:
            coin = overview.get(addr)
            coin_id = coin.get("id") if coin else None
            if not coin_id:
                continue
            id_to_addresses.setdefault(coin_id, []).append(addr)
        if not id_to_addresses:
            return {}
        prices_by_id = self.get_prices(
            symbols=None,
            vs_currencies=vs_currencies,
            timeout=timeout,
            coin_ids=list(id_to_addresses.keys()),
        )
        result: dict[str, dict[str, Dezimal]] = {}
        for coin_id, addr_list in id_to_addresses.items():
            prices = prices_by_id.get(coin_id)
            if not prices:
                continue
            for addr in addr_list:
                result[addr] = dict(prices)
        return result

    def get_prices(
        self,
        symbols: list[str] | None,
        vs_currencies: list[str],
        timeout: int = TIMEOUT,
        coin_ids: list[str] | None = None,
    ) -> dict[str, dict[str, Dezimal]]:
        if coin_ids:
            deduped_ids, vs_param = self._validate_ids_and_prepare(
                coin_ids, vs_currencies
            )
            return self._aggregate_prices_by_ids(deduped_ids, vs_param, timeout)
        if not symbols:
            raise MissingFieldsError(["symbols"])
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

    def _validate_ids_and_prepare(
        self, coin_ids: list[str], vs_currencies: list[str]
    ) -> tuple[list[str], str]:
        if not coin_ids:
            raise MissingFieldsError(["ids"])
        if not vs_currencies:
            raise MissingFieldsError(["vs_currencies"])
        deduped = self._dedupe_items(coin_ids, case_insensitive=True)
        vs_param = ",".join(c.lower() for c in vs_currencies)
        return deduped, vs_param

    def _aggregate_prices_by_ids(
        self, deduped: list[str], vs_param: str, timeout: int
    ) -> dict[str, dict[str, Dezimal]]:
        result: dict[str, dict[str, Dezimal]] = {}
        for chunk in self._chunked(deduped, self.CHUNK_SIZE):
            chunk_result = self._fetch_ids_chunk(chunk, vs_param, timeout)
            self._merge_prices_map(chunk_result, result, key_transform=lambda k: k)
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
        return self._fetch_simple_price(
            [s.lower() for s in chunk], vs_param, timeout, "symbols"
        )

    def _fetch_ids_chunk(
        self, chunk: list[str], vs_param: str, timeout: int
    ) -> dict[str, Any]:
        return self._fetch_simple_price(
            [c.lower() for c in chunk], vs_param, timeout, "ids"
        )

    def _fetch_simple_price(
        self,
        values: list[str],
        vs_param: str,
        timeout: int,
        identifier_key: str,
    ) -> dict[str, Any]:
        return self._fetch(
            "/simple/price",
            params={
                "vs_currencies": vs_param,
                identifier_key: ",".join(values),
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

    def get_asset_details(
        self, provider_id: str, currencies: list[str]
    ) -> CryptoAssetDetails:
        params = {
            "community_data": "false",
            "developer_data": "false",
            "tickers": "false",
            "localization": "false",
        }
        data = self._fetch(f"/coins/{provider_id}", params=params, timeout=self.TIMEOUT)

        platforms_index = self.get_asset_platforms()
        enriched_platforms = self._extract_platforms(data, platforms_index)

        icon_url = self._extract_icon_url(data)
        price_map = self._extract_prices(data, currencies)

        return CryptoAssetDetails(
            name=data.get("name", ""),
            symbol=(data.get("symbol") or "").upper(),
            platforms=enriched_platforms,
            provider=ExternalIntegrationId.COINGECKO,
            provider_id=data.get("id", provider_id),
            price=price_map,
            icon_url=icon_url,
            type=CryptoCurrencyType.TOKEN
            if enriched_platforms
            else CryptoCurrencyType.NATIVE,
        )

    def _extract_platforms(
        self, data: dict[str, Any], platforms_index: dict[str, CryptoPlatform]
    ) -> list[CryptoAssetPlatform]:
        coin_platforms = data.get("platforms") or {}
        enriched_platforms: list[CryptoAssetPlatform] = []

        for platform_id, contract_address in coin_platforms.items():
            if not platform_id or not contract_address:
                continue

            platform_info = platforms_index.get(platform_id)
            platform_name = platform_info.name if platform_info else platform_id
            icon_url = platform_info.icon_url if platform_info else None

            enriched_platforms.append(
                CryptoAssetPlatform(
                    provider_id=platform_id,
                    name=platform_name,
                    contract_address=contract_address,
                    icon_url=icon_url,
                    related_entity_id=None,
                )
            )

        return enriched_platforms

    def _extract_icon_url(self, data: dict[str, Any]) -> str | None:
        image = data.get("image") or {}
        return image.get("large") or image.get("small") or None

    def _extract_prices(
        self, data: dict[str, Any], currencies: list[str]
    ) -> dict[str, Dezimal]:
        market_data = data.get("market_data") or {}
        current_price = market_data.get("current_price") or {}
        price_map: dict[str, Dezimal] = {}

        for currency in currencies:
            currency_lower = currency.lower()
            if currency_lower in current_price:
                try:
                    price_map[currency.upper()] = Dezimal(current_price[currency_lower])
                except Exception:
                    continue

        return price_map

    def get_native_entity_by_platform(
        self, provider_id: str, provider: ExternalIntegrationId
    ) -> Optional[Entity]:
        if provider != ExternalIntegrationId.COINGECKO:
            return None

        return self.ENTITY_CHAIN_MAP.get(provider_id)

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
