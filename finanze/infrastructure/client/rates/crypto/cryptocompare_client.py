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


class CryptoCompareClient:
    BASE_URL = "https://min-api.cryptocompare.com/data"
    ICON_BASE_URL = "https://www.cryptocompare.com"
    TIMEOUT = 10
    COOLDOWN = 0.15
    MAX_SYMBOLS_LEN = 300
    MAX_RETRIES = 3
    BACKOFF_FACTOR = 0.5

    def __init__(self):
        self._log = logging.getLogger(__name__)

    def search(self, symbol: str) -> list[CryptoAsset]:
        if not symbol or not symbol.strip():
            raise MissingFieldsError(["symbol"])
        data = self._fetch("/all/coinlist", params={"fsym": symbol.strip().upper()})
        if data.get("Response") == "Error":
            self._log.info(
                f"CryptoCompare returned no data for symbol {symbol}: {data.get('Message')}"
            )
            return []
        coin_data = data.get("Data", {})
        return self._map_search_results(coin_data)

    def _map_search_results(self, coin_data: dict[str, Any]) -> list[CryptoAsset]:
        assets: list[CryptoAsset] = []
        for raw in coin_data.values():
            mapped = self._map_single_coin(raw)
            if mapped:
                assets.append(mapped)
        return assets

    def _map_single_coin(self, raw: dict[str, Any]) -> CryptoAsset | None:
        try:
            symbol = raw.get("Symbol") or raw.get("Name")
            coin_name = raw.get("CoinName") or raw.get("FullName") or symbol
            if not coin_name or not symbol:
                return None
            image_rel = raw.get("ImageUrl")
            icon_urls: list[str] = []
            if isinstance(image_rel, str) and image_rel:
                icon_urls.append(f"{self.ICON_BASE_URL}/{image_rel.lstrip('/')}")
            return CryptoAsset(
                name=coin_name,
                symbol=symbol,
                icon_urls=icon_urls,
                external_ids={},
            )
        except Exception as e:
            self._log.debug(f"Failed to map cryptocompare coin {raw}: {e}")
            return None

    def get_prices(
        self, symbols: list[str], vs_currencies: list[str], timeout: int = TIMEOUT
    ) -> dict[str, dict[str, Dezimal]]:
        if not symbols:
            raise MissingFieldsError(["symbols"])
        if not vs_currencies:
            raise MissingFieldsError(["vs_currencies"])
        deduped = self._dedupe(symbols)
        tsyms = ",".join(c.upper() for c in vs_currencies)
        result: dict[str, dict[str, Dezimal]] = {}
        for chunk in self._chunk_symbols(deduped):
            fsyms = ",".join(chunk)
            data = self._fetch(
                "/pricemulti", params={"fsyms": fsyms, "tsyms": tsyms}, timeout=timeout
            )
            self._merge_prices(result, data)
        return result

    def _merge_prices(
        self, accumulator: dict[str, dict[str, Dezimal]], data: dict[str, Any]
    ) -> None:
        converted = self._convert_prices(data)
        for k, v in converted.items():
            accumulator[k] = v

    def _dedupe(self, symbols: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for s in symbols:
            su = s.strip().upper()
            if not su:
                continue
            if su in seen:
                continue
            seen.add(su)
            deduped.append(su)
        return deduped

    def _chunk_symbols(self, symbols: list[str]) -> list[list[str]]:
        chunks: list[list[str]] = []
        current: list[str] = []
        current_len = 0
        for sym in symbols:
            sym_len = len(sym)
            if sym_len > self.MAX_SYMBOLS_LEN:
                raise ValueError(
                    f"Symbol {sym} length exceeds max allowed {self.MAX_SYMBOLS_LEN}"
                )
            if not current:
                # start new chunk
                current = [sym]
                current_len = sym_len
                continue
            proposed_len = current_len + 1 + sym_len  # +1 for comma
            if proposed_len <= self.MAX_SYMBOLS_LEN:
                current.append(sym)
                current_len = proposed_len
            else:
                chunks.append(current)
                current = [sym]
                current_len = sym_len
        if current:
            chunks.append(current)
        return chunks

    def _convert_prices(self, data: dict[str, Any]) -> dict[str, dict[str, Dezimal]]:
        result: dict[str, dict[str, Dezimal]] = {}
        for sym, prices in data.items():
            if not isinstance(prices, dict):
                continue
            converted: dict[str, Dezimal] = {}
            for cur, val in prices.items():
                try:
                    converted[cur.upper()] = Dezimal(val)
                except Exception:
                    continue
            if converted:
                result[sym.upper()] = converted
        return result

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
                backoff_factor=self.BACKOFF_FACTOR,
                cooldown=self.COOLDOWN,
                log=self._log,
            )
        except requests.Timeout as e:
            self._log.warning(f"Timeout calling CryptoCompare endpoint {url}")
            raise e
        except requests.RequestException as e:
            self._log.error(f"Request error calling CryptoCompare endpoint {url}: {e}")
            raise e

        if not response.ok:
            status = response.status_code
            body = response.text
            if status == 429:
                raise TooManyRequests()
            if status in (401, 403):
                raise InvalidProvidedCredentials()
            if status == 400:
                self._log.error(f"Bad request to CryptoCompare {url}: {body}")
                raise ValueError("Invalid request to CryptoCompare API")
            if status in (500, 503):
                self._log.error(f"CryptoCompare service error {status}: {body}")
                response.raise_for_status()
            if status == 408:
                self._log.warning(f"CryptoCompare timeout status for {url}: {body}")
                response.raise_for_status()
            self._log.error(
                f"Unexpected CryptoCompare response {status} for {url}: {body}"
            )
            response.raise_for_status()

        try:
            return response.json()
        except ValueError:
            self._log.error(
                f"Failed to decode JSON from CryptoCompare for {url}: {response.text[:200]}"
            )
            raise
