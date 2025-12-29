import logging
from uuid import uuid4

from domain.crypto import CryptoFetchRequest, CryptoCurrencyType
from domain.dezimal import Dezimal
from domain.exception.exceptions import ExternalIntegrationRequired
from domain.external_integration import (
    EnabledExternalIntegrations,
    ExternalIntegrationId,
)
from domain.global_position import (
    CryptoCurrencyPosition,
    CryptoCurrencyWallet,
)
from infrastructure.client.crypto.etherscan.etherscan_client import EtherscanClient


class EtherscanFetcher:
    def __init__(
        self,
        client: EtherscanClient,
        chain_id: int,
        native_symbol: str,
        scale: Dezimal,
    ):
        self.etherscan_client = client
        self.chain_id = chain_id
        self.scale = scale
        self.native_symbol = native_symbol

        self._log = logging.getLogger(__name__)

    def fetch(self, request: CryptoFetchRequest) -> CryptoCurrencyWallet:
        amount = (
            Dezimal(
                self._fetch(
                    module="account",
                    action="balance",
                    address=request.address,
                    integrations=request.integrations,
                )
            )
            * self.scale
        )

        assets = [
            CryptoCurrencyPosition(
                id=uuid4(),
                symbol=self.native_symbol,
                amount=amount,
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
                contract_address=contract_address.lower(),
                name=token_tx.get("tokenName"),
                symbol=symbol,
                amount=amount,
                type=CryptoCurrencyType.TOKEN,
            )

        return CryptoCurrencyWallet(
            id=request.connection_id,
            assets=assets + list(tokens.values()),
        )

    def _fetch(self, integrations: EnabledExternalIntegrations, *args, **kwargs) -> any:
        if ExternalIntegrationId.ETHERSCAN not in integrations:
            raise ExternalIntegrationRequired([ExternalIntegrationId.ETHERSCAN])

        return self.etherscan_client.fetch(
            chain_id=self.chain_id,
            credentials=integrations[ExternalIntegrationId.ETHERSCAN],
            *args,
            **kwargs,
        )
