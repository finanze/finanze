import logging
from typing import Any
from uuid import uuid4

from domain.crypto import (
    CryptoFetchRequest,
    CryptoCurrencyType,
    CryptoFetchResults,
    CryptoFetchResult,
    CryptoFetchedPosition,
)
from domain.dezimal import Dezimal
from domain.exception.exceptions import ExternalIntegrationRequired, AddressNotFound
from domain.external_integration import (
    EnabledExternalIntegrations,
    ExternalIntegrationId,
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

    async def fetch(self, request: CryptoFetchRequest) -> CryptoFetchResults:
        results: dict[str, CryptoFetchResult | None] = {}

        for address in request.addresses:
            try:
                amount = (
                    Dezimal(
                        await self._fetch(
                            module="account",
                            action="balance",
                            address=address,
                            integrations=request.integrations,
                        )
                    )
                    * self.scale
                )
            except AddressNotFound:
                results[address] = None
                continue

            assets = [
                CryptoFetchedPosition(
                    id=uuid4(),
                    symbol=self.native_symbol,
                    balance=amount,
                    type=CryptoCurrencyType.NATIVE,
                )
            ]

            token_txs = await self._fetch(
                module="account",
                action="tokentx",
                address=address,
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
                token_amount = (
                    Dezimal(
                        await self._fetch(
                            module="account",
                            action="tokenbalance",
                            address=address,
                            contract_address=contract_address,
                            integrations=request.integrations,
                        )
                    )
                    * scale
                )

                tokens[contract_address] = CryptoFetchedPosition(
                    id=uuid4(),
                    contract_address=contract_address.lower(),
                    name=token_tx.get("tokenName"),
                    symbol=symbol,
                    balance=token_amount,
                    type=CryptoCurrencyType.TOKEN,
                )

            results[address] = CryptoFetchResult(
                address=address,
                assets=assets + list(tokens.values()),
            )

        return CryptoFetchResults(results=results)

    async def _fetch(
        self, integrations: EnabledExternalIntegrations, *args, **kwargs
    ) -> Any:
        if ExternalIntegrationId.ETHERSCAN not in integrations:
            raise ExternalIntegrationRequired([ExternalIntegrationId.ETHERSCAN])

        return await self.etherscan_client.fetch(
            chain_id=self.chain_id,
            credentials=integrations[ExternalIntegrationId.ETHERSCAN],
            *args,
            **kwargs,
        )
