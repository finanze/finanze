import asyncio
import logging
from asyncio import Lock
from dataclasses import asdict
from uuid import UUID, uuid4

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.config_port import ConfigPort
from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from application.ports.crypto_price_provider import CryptoPriceProvider
from application.ports.crypto_wallet_connection_port import CryptoWalletConnectionPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from domain import native_entities
from domain.crypto import CryptoFetchRequest
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityType
from domain.exception.exceptions import EntityNotFound, ExecutionConflict
from domain.fetch_result import FetchOptions, FetchRequest, FetchResult, FetchResultCode
from domain.fetched_data import FetchedData
from domain.global_position import (
    CryptoCurrencies,
    CryptoCurrencyToken,
    CryptoCurrencyWallet,
    GlobalPosition,
    Investments,
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
        transaction_handler_port: TransactionHandlerPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)

        self._position_port = position_port
        self._entity_fetchers = entity_fetchers
        self._crypto_wallet_connection_port = crypto_wallet_connection_port
        self._crypto_price_provider = crypto_price_provider
        self._config_port = config_port

        self._locks: dict[UUID, Lock] = {}

        self._log = logging.getLogger(__name__)

    def _get_lock(self, entity_id: UUID) -> Lock:
        if entity_id not in self._locks:
            self._locks[entity_id] = asyncio.Lock()
        return self._locks[entity_id]

    async def execute(self, fetch_request: FetchRequest) -> FetchResult:
        entity_id = fetch_request.entity_id
        if entity_id:
            entity = native_entities.get_native_by_id(
                entity_id, EntityType.CRYPTO_WALLET
            )
            if not entity:
                raise EntityNotFound(entity_id)
            entities = [entity]
        else:
            entities = [
                e
                for e in native_entities.NATIVE_ENTITIES
                if e.type == EntityType.CRYPTO_WALLET
            ]

        fetched_data = []
        for entity in entities:
            lock = self._get_lock(entity_id)

            if lock.locked():
                raise ExecutionConflict()

            async with lock:
                specific_fetcher = self._entity_fetchers[entity]

                fetched_data.append(
                    self.get_data(entity, specific_fetcher, fetch_request.fetch_options)
                )

        return FetchResult(FetchResultCode.COMPLETED, data=fetched_data)

    def get_data(
        self,
        entity: Entity,
        specific_fetcher: CryptoEntityFetcher,
        options: FetchOptions,
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
                )
            )
            wallet = self._update_market_value(wallet)
            wallets.append(wallet)

        position = GlobalPosition(
            id=uuid4(),
            entity=entity,
            investments=Investments(
                crypto_currencies=CryptoCurrencies(details=wallets)
            ),
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
                        market_value=self._get_market_value(token.symbol, token.amount),
                        currency=TARGET_FIAT,
                    )
                )

        market_value = self._get_market_value(wallet.symbol, wallet.amount)
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

    def _get_market_value(self, crypto_symbol: str, crypto_amount: Dezimal) -> Dezimal:
        return round(
            crypto_amount
            * self._crypto_price_provider.get_price(crypto_symbol, TARGET_FIAT),
            2,
        )
