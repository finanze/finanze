import logging

from application.ports.crypto_price_provider import CryptoAssetInfoProvider
from cachetools import TTLCache, cached
from domain.crypto import CryptoAsset
from domain.dezimal import Dezimal
from infrastructure.client.rates.crypto.coingecko_client import CoinGeckoClient
from infrastructure.client.rates.crypto.cryptocompare_client import CryptoCompareClient
from infrastructure.client.rates.crypto.p2s_client import P2SClient


class CryptoAssetInfoClient(CryptoAssetInfoProvider):
    PRICE_CACHE_TTL = 20 * 60

    def __init__(self):
        self._p2s_client = P2SClient()
        self._coingecko_client = CoinGeckoClient()
        self._cc_client = CryptoCompareClient()

        self._log = logging.getLogger(__name__)

    @cached(
        cache=TTLCache(maxsize=200, ttl=PRICE_CACHE_TTL),
        key=lambda _,
        symbol,
        fiat_iso,
        **kwargs: f"{symbol.upper()}_{fiat_iso.upper()}",
    )
    def get_price(self, symbol: str, fiat_iso: str, **kwargs) -> Dezimal:
        timeout = kwargs.get("timeout")
        if self._p2s_client.supports_symbol(symbol):
            return self._p2s_client.get_price(symbol, fiat_iso, timeout)

        return (
            self.get_multiple_prices_by_symbol([symbol], [fiat_iso])
            .get(symbol, {})
            .get(fiat_iso, Dezimal(1))
        )

    @cached(
        cache=TTLCache(maxsize=10, ttl=PRICE_CACHE_TTL),
        key=lambda _, symbols, fiat_isos, **kwargs: hash(
            f"{','.join(sorted(symbols)).upper()}_{','.join(sorted(fiat_isos)).upper()}"
        ),
    )
    def get_multiple_prices_by_symbol(
        self, symbols: list[str], fiat_isos: list[str], **kwargs
    ) -> dict[str, dict[str, Dezimal]]:
        timeout = kwargs.get("timeout")
        result = {}

        coingecko_prices = self._cc_client.get_prices(symbols, fiat_isos, timeout)
        for sym, prices in coingecko_prices.items():
            result[sym] = prices

        missing_symbols = [s for s in symbols if s not in result]
        if missing_symbols:
            missing_prices = self._coingecko_client.get_prices(
                missing_symbols, fiat_isos, timeout
            )
            for sym, prices in missing_prices.items():
                result[sym] = prices

        # { crypto_symbol: { fiat_iso: Dezimal(price) } }
        return result

    @cached(
        cache=TTLCache(maxsize=50, ttl=PRICE_CACHE_TTL),
        key=lambda _, addresses, fiat_isos, **kwargs: hash(
            f"{','.join(sorted(a.lower() for a in addresses))}_{','.join(sorted(f.upper() for f in fiat_isos))}"
        ),
    )
    def get_prices_by_addresses(
        self, addresses: list[str], fiat_isos: list[str], **kwargs
    ) -> dict[str, dict[str, Dezimal]]:
        timeout = kwargs.get("timeout")
        return self._coingecko_client.get_prices_by_addresses(
            addresses, fiat_isos, timeout or self._coingecko_client.TIMEOUT
        )

    @cached(cache=TTLCache(maxsize=200, ttl=86400))
    def get_by_symbol(self, symbol: str) -> list[CryptoAsset]:
        try:
            assets = self._cc_client.search(symbol)
            if assets:
                return assets
        except Exception as e:
            self._log.error(f"CryptoCompare search failed for {symbol}: {e}")

        self._log.info(f"Backing off to CoinGecko search for symbol {symbol}")
        return self._coingecko_client.search(symbol)

    def get_multiple_overview_by_addresses(
        self, addresses: list[str]
    ) -> dict[str, CryptoAsset]:
        if not addresses:
            return {}
        overview = self._coingecko_client.get_coin_overview_by_addresses(addresses)
        result: dict[str, CryptoAsset] = {}
        for raw, coin in overview.items():
            asset = CryptoAsset(
                name=coin.get("name"),
                symbol=coin.get("symbol"),
                icon_urls=[],
                external_ids={"COINGECKO": coin.get("id")},
            )
            result[raw] = asset
        return result
