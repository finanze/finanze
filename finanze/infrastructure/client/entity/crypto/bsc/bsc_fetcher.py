import logging
from uuid import uuid4

from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from domain.crypto import CryptoFetchIntegrations, CryptoFetchRequest
from domain.dezimal import Dezimal
from domain.exception.exceptions import ExternalIntegrationRequired
from domain.external_integration import ExternalIntegrationId
from domain.global_position import (
    CryptoCurrencyPosition,
    CryptoCurrencyType,
    CryptoCurrencyWallet,
)
from infrastructure.client.crypto.etherscan.etherscan_client import EtherscanClient


class BSCFetcher(CryptoEntityFetcher):
    CHAIN_ID = 56
    SCALE = Dezimal("1e-18")

    def __init__(self, etherscan_client: EtherscanClient):
        self.etherscan_client = etherscan_client

        self._log = logging.getLogger(__name__)

    def fetch(self, request: CryptoFetchRequest) -> CryptoCurrencyWallet:
        bnb_amount = (
            Dezimal(
                self._fetch(
                    module="account",
                    action="balance",
                    address=request.address,
                    integrations=request.integrations,
                )
            )
            * self.SCALE
        )

        assets = [
            CryptoCurrencyPosition(
                id=uuid4(),
                symbol="BNB",
                amount=bnb_amount,
                type=CryptoCurrencyType.NATIVE,
            )
        ]

        token_txs = self._fetch(
            module="account",
            action="tokentx",
            address=request.address,
            start_block=0,
            end_block=99999999,
            sort="asc",
            integrations=request.integrations,
        )

        tokens = {}
        for token_tx in token_txs:
            contract_address = token_tx["contractAddress"]
            if contract_address in tokens:
                continue

            symbol = token_tx.get("tokenSymbol")
            decimals = token_tx["tokenDecimal"]
            scale = Dezimal(f"1e-{decimals}")
            amount = (
                Dezimal(
                    self._fetch(
                        module="account",
                        action="tokenbalance",
                        address=request.address,
                        contract_address=contract_address,
                        integrations=request.integrations,
                    )
                )
                * scale
            )

            tokens[contract_address] = CryptoCurrencyPosition(
                id=uuid4(),
                contract_address=contract_address,
                name=token_tx.get("tokenName"),
                symbol=symbol,
                amount=amount,
                type=CryptoCurrencyType.TOKEN,
            )

        return CryptoCurrencyWallet(
            id=request.connection_id,
            assets=assets + list(tokens.values()),
        )

    def _fetch(self, integrations: CryptoFetchIntegrations, *args, **kwargs) -> any:
        if not integrations.etherscan:
            raise ExternalIntegrationRequired([ExternalIntegrationId.ETHERSCAN])
        return self.etherscan_client.fetch(
            chain_id=self.CHAIN_ID, credentials=integrations.etherscan, *args, **kwargs
        )
