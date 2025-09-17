import asyncio
import logging
from asyncio import Lock
from dataclasses import asdict
from datetime import datetime
from typing import List
from uuid import UUID, uuid4

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.config_port import ConfigPort
from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from application.ports.crypto_price_provider import CryptoPriceProvider
from application.ports.crypto_wallet_connection_port import CryptoWalletConnectionPort
from application.ports.last_fetches_port import LastFetchesPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.use_cases.connect_crypto_wallet import from_config
from dateutil.tz import tzlocal
from domain import native_entities
from domain.crypto import CryptoFetchIntegrations, CryptoFetchRequest
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityType, Feature
from domain.exception.exceptions import (
    EntityNotFound,
    ExecutionConflict,
    ExternalIntegrationRequired,
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
    CryptoAsset,
    CryptoCurrencies,
    CryptoCurrencyToken,
    CryptoCurrencyWallet,
    GlobalPosition,
    ProductType,
)
from domain.use_cases.fetch_crypto_data import FetchCryptoData

TARGET_FIAT = "EUR"


class FetchCryptoDataImpl(AtomicUCMixin, FetchCryptoData):
    def __init__(
        self,
        position_port: PositionPort,
        entity_fetchers: dict[Entity, CryptoEntityFetcher],
        crypto_wallet_connection_port: CryptoWalletConnectionPort,
        crypto_price_provider: CryptoPriceProvider,
        config_port: ConfigPort,
        last_fetches_port: LastFetchesPort,
        transaction_handler_port: TransactionHandlerPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)

        self._position_port = position_port
        self._entity_fetchers = entity_fetchers
        self._crypto_wallet_connection_port = crypto_wallet_connection_port
        self._crypto_price_provider = crypto_price_provider
        self._last_fetches_port = last_fetches_port
        self._config_port = config_port

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

        integrations = from_config(self._config_port.load().integrations)

        fetched_data = []
        for entity in entities:
            lock = self._get_lock(entity.id)

            if lock.locked():
                raise ExecutionConflict()

            async with lock:
                specific_fetcher = self._entity_fetchers[entity]

                try:
                    fetched_data.append(
                        self.get_data(
                            entity,
                            specific_fetcher,
                            fetch_request.fetch_options,
                            integrations,
                        )
                    )

                    self._update_last_fetch(entity.id, [Feature.POSITION])
                except ExternalIntegrationRequired:
                    pass

        return FetchResult(FetchResultCode.COMPLETED, data=fetched_data)

    def get_data(
        self,
        entity: Entity,
        specific_fetcher: CryptoEntityFetcher,
        options: FetchOptions,
        integrations: CryptoFetchIntegrations,
    ) -> FetchedData:
        existing_connections = self._crypto_wallet_connection_port.get_by_entity_id(
            entity.id
        )

        wallets = []
        for connection in existing_connections:
            wallet = specific_fetcher.fetch(
                CryptoFetchRequest(
                    connection_id=connection.id,
                    address=connection.address,
                    integrations=integrations,
                )
            )
            wallet = self._update_market_value(wallet)
            wallets.append(wallet)

        products = {ProductType.CRYPTO: CryptoCurrencies(wallets)}

        position = GlobalPosition(
            id=uuid4(),
            entity=entity,
            products=products,
        )

        self._position_port.save(position)

        fetched_data = FetchedData(
            position=position,
        )
        return fetched_data

    def _update_market_value(
        self, wallet: CryptoCurrencyWallet
    ) -> CryptoCurrencyWallet:
        tokens = []
        if wallet.tokens is not None:
            for token in wallet.tokens:
                token_dict = asdict(token)
                del token_dict["market_value"]
                del token_dict["currency"]
                tokens.append(
                    CryptoCurrencyToken(
                        **token_dict,
                        market_value=self._get_market_value(token.token, token.amount),
                        currency=TARGET_FIAT,
                    )
                )

        market_value = self._get_market_value(wallet.crypto, wallet.amount)
        wallet_dict = asdict(wallet)
        del wallet_dict["market_value"]
        del wallet_dict["currency"]
        del wallet_dict["tokens"]
        return CryptoCurrencyWallet(
            **wallet_dict,
            market_value=market_value,
            currency=TARGET_FIAT,
            tokens=tokens,
        )

    def _get_market_value(self, crypto: CryptoAsset, crypto_amount: Dezimal) -> Dezimal:
        return round(
            crypto_amount * self._crypto_price_provider.get_price(crypto, TARGET_FIAT),
            2,
        )

    def _update_last_fetch(self, entity_id: UUID, features: List[Feature]):
        now = datetime.now(tzlocal())
        records = []
        for feature in features:
            records.append(FetchRecord(entity_id=entity_id, feature=feature, date=now))
        self._last_fetches_port.save(records)
