import asyncio
import logging
import os
from asyncio import Lock
from dataclasses import asdict
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from application.ports.crypto_asset_port import CryptoAssetRegistryPort
from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from application.ports.crypto_price_provider import CryptoAssetInfoProvider
from application.ports.crypto_wallet_connection_port import CryptoWalletConnectionPort
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.last_fetches_port import LastFetchesPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.use_cases.fetch_financial_data import handle_cooldown
from dateutil.tz import tzlocal
from domain import native_entities
from domain.crypto import (
    CryptoFetchRequest,
)
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityType, Feature
from domain.exception.exceptions import (
    EntityNotFound,
    ExecutionConflict,
)
from domain.external_integration import (
    EnabledExternalIntegrations,
    ExternalIntegrationType,
)
from domain.fetch_record import FetchRecord
from domain.fetch_result import (
    FetchedData,
    FetchOptions,
    FetchRequest,
    FetchResult,
    FetchResultCode,
)
from domain.global_position import (
    CryptoCurrencies,
    CryptoCurrencyPosition,
    CryptoCurrencyType,
    CryptoCurrencyWallet,
    GlobalPosition,
    ProductType,
)
from domain.use_cases.fetch_crypto_data import FetchCryptoData

TARGET_FIAT = "EUR"
CRYPTO_POSITION_UPDATE_COOLDOWN = int(
    os.environ.get("CRYPTO_POSITION_UPDATE_COOLDOWN", 120)
)


class FetchCryptoDataImpl(FetchCryptoData):
    def __init__(
        self,
        position_port: PositionPort,
        entity_fetchers: dict[Entity, CryptoEntityFetcher],
        crypto_wallet_connection_port: CryptoWalletConnectionPort,
        crypto_asset_registry_port: CryptoAssetRegistryPort,
        crypto_asset_info_provider: CryptoAssetInfoProvider,
        last_fetches_port: LastFetchesPort,
        external_integration_port: ExternalIntegrationPort,
        transaction_handler_port: TransactionHandlerPort,
    ):
        self._position_port = position_port
        self._entity_fetchers = entity_fetchers
        self._crypto_wallet_connection_port = crypto_wallet_connection_port
        self._crypto_asset_info_provider = crypto_asset_info_provider
        self._crypto_asset_registry_port = crypto_asset_registry_port
        self._last_fetches_port = last_fetches_port
        self._external_integration_port = external_integration_port
        self._transaction_handler_port = transaction_handler_port

        self._locks: dict[UUID, Lock] = {}

        self._log = logging.getLogger(__name__)

    def _get_lock(self, entity_id: UUID) -> Lock:
        if entity_id not in self._locks:
            self._locks[entity_id] = asyncio.Lock()
        return self._locks[entity_id]

    async def execute(self, fetch_request: FetchRequest) -> FetchResult:
        entity_id = fetch_request.entity_id

        connected_entities = (
            self._crypto_wallet_connection_port.get_connected_entities()
        )

        if entity_id:
            entity = native_entities.get_native_by_id(
                entity_id, EntityType.CRYPTO_WALLET
            )
            if not entity:
                raise EntityNotFound(entity_id)
            if entity_id not in connected_entities:
                return FetchResult(FetchResultCode.NOT_CONNECTED)
            entities = [entity]
        else:
            entities = [
                e for e in native_entities.NATIVE_ENTITIES if e.id in connected_entities
            ]

        for entity in entities:
            last_fetch = self._last_fetches_port.get_by_entity_id(entity.id)
            result = handle_cooldown(last_fetch, CRYPTO_POSITION_UPDATE_COOLDOWN)
            if result:
                return result

        enabled_integrations = self._external_integration_port.get_payloads_by_type(
            ExternalIntegrationType.CRYPTO_PROVIDER
        )

        fetched_data = []
        exception = None
        for entity in entities:
            lock = self._get_lock(entity.id)

            if lock.locked():
                raise ExecutionConflict()

            async with lock:
                specific_fetcher = self._entity_fetchers[entity]

                try:
                    fetched_data.append(
                        await self.get_data(
                            entity,
                            specific_fetcher,
                            fetch_request.fetch_options,
                            enabled_integrations,
                        )
                    )
                except Exception as e:
                    self._log.exception(e)
                    exception = e

        code = (
            FetchResultCode.COMPLETED
            if not exception
            else FetchResultCode.PARTIALLY_COMPLETED
        )
        if exception and len(entities) == 1:
            raise exception

        return FetchResult(code, data=fetched_data)

    async def get_data(
        self,
        entity: Entity,
        specific_fetcher: CryptoEntityFetcher,
        options: FetchOptions,
        integrations: EnabledExternalIntegrations,
    ) -> FetchedData:
        existing_connections = self._crypto_wallet_connection_port.get_by_entity_id(
            entity.id
        )

        fetch_requests = []
        for connection in existing_connections:
            fetch_requests.append(
                CryptoFetchRequest(
                    connection_id=connection.id,
                    address=connection.address,
                    integrations=integrations,
                )
            )

        candidate_wallets = []
        try:
            candidate_wallets = specific_fetcher.fetch_multiple(fetch_requests)
        except NotImplementedError:
            for fetch_request in fetch_requests:
                wallet = specific_fetcher.fetch(fetch_request)
                candidate_wallets.append(wallet)

        wallets_by_id = {wallet.id: wallet for wallet in candidate_wallets}
        for connection in existing_connections:
            wallet = wallets_by_id[connection.id]
            wallet.name = connection.name
            wallet.address = connection.address

        contract_addresses = set()
        native_symbols = set()
        for wallet in candidate_wallets:
            for asset in wallet.assets:
                if asset.type == CryptoCurrencyType.TOKEN and asset.contract_address:
                    contract_addresses.add(asset.contract_address.lower())
                elif asset.type == CryptoCurrencyType.NATIVE:
                    native_symbols.add(asset.symbol)

        price_map = self._get_price_map(contract_addresses, native_symbols)

        wallets = []
        for w in candidate_wallets:
            wallet = self._process_wallet_data(w, price_map)
            wallets.append(wallet)

        products = {ProductType.CRYPTO: CryptoCurrencies(wallets)}

        position = GlobalPosition(
            id=uuid4(),
            entity=entity,
            products=products,
        )

        async with self._transaction_handler_port.start():
            self._position_port.save(position)

            self._update_last_fetch(entity.id, [Feature.POSITION])

            return FetchedData(
                position=position,
            )

    def _process_wallet_data(
        self, wallet: CryptoCurrencyWallet, price_map: dict[str, Dezimal]
    ) -> CryptoCurrencyWallet:
        assets = []
        if wallet.assets:
            for asset in wallet.assets:
                asset_dict = asdict(asset)
                market_value = self._get_market_value(price_map, asset)
                asset_dict["market_value"] = market_value
                asset_dict["currency"] = TARGET_FIAT
                asset_details = self._crypto_asset_registry_port.get_by_symbol(
                    asset.symbol
                )
                asset_info = asset_details
                if (market_value is not None and asset.amount > 0) and not asset_info:
                    candidate_assets = self._crypto_asset_info_provider.get_by_symbol(
                        asset.symbol
                    )
                    if candidate_assets:
                        asset_info = candidate_assets[0]
                        asset_info.id = uuid4()
                        self._crypto_asset_registry_port.save(asset_info)

                if asset_info and market_value is None:
                    asset_info = None

                if asset_info:
                    asset_dict["name"] = asset_info.name
                asset_dict["crypto_asset"] = asset_info
                position = CryptoCurrencyPosition(**asset_dict)
                if position.name:
                    position.name = position.name[:150]
                if position.symbol:
                    position.symbol = position.symbol[:30]
                assets.append(position)

        wallet_dict = asdict(wallet)
        wallet_dict["assets"] = assets
        return CryptoCurrencyWallet(**wallet_dict)

    def _get_price_map(
        self,
        contract_addresses: set[str],
        native_symbols: set[str],
    ) -> dict[str, Dezimal]:
        price_map: dict[str, Dezimal] = {}
        if native_symbols:
            symbol_prices = (
                self._crypto_asset_info_provider.get_multiple_prices_by_symbol(
                    list(native_symbols), fiat_isos=[TARGET_FIAT]
                )
            )
            for symbol in native_symbols:
                upper = symbol.upper()
                fiat_prices = symbol_prices.get(upper)
                if fiat_prices and TARGET_FIAT in fiat_prices:
                    price_map[upper] = fiat_prices[TARGET_FIAT]

        if contract_addresses:
            address_prices = self._crypto_asset_info_provider.get_prices_by_addresses(
                list(contract_addresses), fiat_isos=[TARGET_FIAT]
            )
            for addr, fiat_prices in address_prices.items():
                fiat_price = fiat_prices.get(TARGET_FIAT)
                if fiat_price is not None:
                    price_map[addr.lower()] = fiat_price

        return price_map

    def _get_market_value(
        self, price_map: dict[str, Dezimal], crypto_currency: CryptoCurrencyPosition
    ) -> Optional[Dezimal]:
        if crypto_currency.amount <= 0:
            return Dezimal(0)

        price_key = (
            crypto_currency.symbol
            if crypto_currency.type == CryptoCurrencyType.NATIVE
            else crypto_currency.contract_address.lower()
        )
        price = price_map.get(price_key) if price_key else None
        if price is None:
            return None
        return round(crypto_currency.amount * price, 2)

    def _update_last_fetch(self, entity_id: UUID, features: List[Feature]):
        now = datetime.now(tzlocal())
        records = []
        for feature in features:
            records.append(FetchRecord(entity_id=entity_id, feature=feature, date=now))
        self._last_fetches_port.save(records)
