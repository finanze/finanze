from contextlib import asynccontextmanager
from typing import List, Optional
from uuid import UUID, uuid4

import pytest

from application.ports.crypto_asset_port import CryptoAssetRegistryPort
from application.ports.crypto_entity_fetcher import CryptoEntityFetcher
from application.ports.crypto_price_provider import CryptoAssetInfoProvider
from application.ports.crypto_wallet_port import CryptoWalletPort
from application.ports.external_integration_port import ExternalIntegrationPort
from application.ports.last_fetches_port import LastFetchesPort
from application.ports.position_port import PositionPort
from application.ports.public_key_derivation import PublicKeyDerivation
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.use_cases.fetch_crypto_data import (
    FetchCryptoDataImpl,
    UNUSED_GAP,
    DERIVATION_BATCH_SIZE,
)
from domain import native_entities
from domain.crypto import (
    AddressSource,
    CryptoAsset,
    CryptoFetchedPosition,
    CryptoFetchRequest,
    CryptoFetchResult,
    CryptoFetchResults,
    CryptoCurrencyType,
    CryptoWallet,
    HDAddress,
    HDWallet,
)
from domain.dezimal import Dezimal
from domain.entity import Feature
from domain.external_integration import EnabledExternalIntegrations
from domain.fetch_record import FetchRecord
from domain.fetch_result import FetchRequest, FetchResultCode
from domain.public_key import (
    AddressDerivationRequest,
    CoinType,
    DerivedAddress,
    DerivedAddressesResult,
    ScriptType,
)

BITCOIN_ENTITY = native_entities.BITCOIN
BITCOIN_ID = BITCOIN_ENTITY.id


class MockPositionPort(PositionPort):
    def __init__(self):
        self.saved = []

    async def save(self, position):
        self.saved.append(position)

    async def get_by_id(self, position_id):
        return None

    async def get_last_grouped_by_entity(self, query=None):
        return {}

    async def delete_position_for_date(self, entity_id, date, source):
        pass

    async def delete_by_id(self, position_id):
        pass

    async def get_stock_detail(self, entry_id):
        return None

    async def get_fund_detail(self, entry_id):
        return None

    async def update_market_value(self, entry_id, product_type, market_value):
        pass


class MockCryptoWalletPort(CryptoWalletPort):
    def __init__(self, wallets: list[CryptoWallet] = None):
        self._wallets = wallets or []
        self.inserted_hd_addresses: dict[UUID, list[HDAddress]] = {}

    async def get_by_entity_id(
        self, entity_id: UUID, hd_addresses: bool
    ) -> List[CryptoWallet]:
        return [w for w in self._wallets if w.entity_id == entity_id]

    async def exists_by_entity_and_address(self, entity_id: UUID, address: str) -> bool:
        return False

    async def exists_by_entity_and_xpub(self, entity_id: UUID, xpub: str) -> bool:
        return False

    async def get_connected_entities(self) -> set[UUID]:
        return {w.entity_id for w in self._wallets}

    async def insert(self, connection: CryptoWallet):
        self._wallets.append(connection)

    async def insert_hd_wallet(self, wallet_id: UUID, hd_wallet: HDWallet):
        pass

    async def insert_hd_addresses(self, wallet_id: UUID, addresses: list[HDAddress]):
        self.inserted_hd_addresses[wallet_id] = addresses

    async def rename(self, wallet_connection_id: UUID, name: str):
        pass

    async def delete(self, wallet_connection_id: UUID):
        pass


class MockCryptoEntityFetcher(CryptoEntityFetcher):
    def __init__(self, results_fn=None):
        self._results_fn = results_fn
        self.fetch_calls: list[CryptoFetchRequest] = []

    async def fetch(self, request: CryptoFetchRequest) -> CryptoFetchResults:
        self.fetch_calls.append(request)
        if self._results_fn:
            return self._results_fn(request)

        results = {}
        for addr in request.addresses:
            results[addr] = CryptoFetchResult(
                address=addr,
                has_txs=False,
                assets=[
                    CryptoFetchedPosition(
                        id=uuid4(),
                        symbol="BTC",
                        balance=Dezimal("0.5"),
                        type=CryptoCurrencyType.NATIVE,
                    )
                ],
            )
        return CryptoFetchResults(results=results)


class MockCryptoAssetRegistryPort(CryptoAssetRegistryPort):
    async def get_by_symbol(self, symbol: str) -> Optional[CryptoAsset]:
        return None

    async def save(self, asset: CryptoAsset):
        pass


class MockCryptoAssetInfoProvider(CryptoAssetInfoProvider):
    async def get_by_symbol(self, symbol: str):
        return []

    async def get_multiple_prices_by_symbol(self, symbols, fiat_isos=None):
        result = {}
        for s in symbols:
            result[s.upper()] = {"EUR": Dezimal("50000")}
        return result

    async def get_prices_by_addresses(self, addresses, fiat_isos=None):
        return {}

    async def get_price(self, symbol, fiat_iso, **kwargs):
        return Dezimal(0)

    async def get_multiple_overview_by_addresses(self, addresses):
        return {}

    async def asset_lookup(self, symbol=None, name=None):
        return []

    async def get_asset_platforms(self):
        return {}

    async def get_asset_details(self, provider_id, currencies, provider=None):
        return None

    async def get_native_entity_by_platform(self, provider_id, provider):
        return None


class MockLastFetchesPort(LastFetchesPort):
    async def get_by_entity_id(self, entity_id: UUID):
        return None

    async def save(self, records: list[FetchRecord]):
        pass


class MockExternalIntegrationPort(ExternalIntegrationPort):
    async def get_payloads_by_type(
        self, integration_type
    ) -> EnabledExternalIntegrations:
        return {}

    async def get_all(self):
        return []

    async def activate(self, integration, payload):
        pass

    async def deactivate(self, integration):
        pass

    async def get_payload(self, integration):
        return None


class MockTransactionHandlerPort(TransactionHandlerPort):
    @asynccontextmanager
    async def start(self):
        yield


class MockPublicKeyDerivation(PublicKeyDerivation):
    def calculate(self, request: AddressDerivationRequest) -> DerivedAddressesResult:
        receiving = [
            DerivedAddress(
                index=i,
                path=f"m/84'/0'/0/{i}",
                address=f"recv_{i}",
                pubkey=f"pub_recv_{i}",
                change=0,
            )
            for i in range(request.receiving_range[0], request.receiving_range[1])
        ]
        change = [
            DerivedAddress(
                index=i,
                path=f"m/84'/0'/1/{i}",
                address=f"change_{i}",
                pubkey=f"pub_change_{i}",
                change=1,
            )
            for i in range(request.change_range[0], request.change_range[1])
        ]
        return DerivedAddressesResult(
            key_type="xpub",
            script_type=request.script_type or ScriptType.P2WPKH,
            coin=request.coin,
            receiving=receiving,
            change=change,
            base_path="m/84'/0'/0'",
        )


def _make_manual_wallet(entity_id=BITCOIN_ID, addresses=None):
    return CryptoWallet(
        id=uuid4(),
        entity_id=entity_id,
        addresses=addresses or ["addr_manual_1"],
        name="Manual Wallet",
        address_source=AddressSource.MANUAL,
        hd_wallet=None,
    )


def _make_derived_wallet(entity_id=BITCOIN_ID, hd_addresses=None):
    wallet_id = uuid4()
    return CryptoWallet(
        id=wallet_id,
        entity_id=entity_id,
        addresses=[],
        name="Derived Wallet",
        address_source=AddressSource.DERIVED,
        hd_wallet=HDWallet(
            xpub="xpub_test",
            addresses=hd_addresses or [],
            script_type=ScriptType.P2WPKH,
            coin_type=CoinType.BITCOIN,
        ),
    )


@pytest.fixture
def position_port():
    return MockPositionPort()


@pytest.fixture
def crypto_asset_registry():
    return MockCryptoAssetRegistryPort()


@pytest.fixture
def crypto_asset_info():
    return MockCryptoAssetInfoProvider()


@pytest.fixture
def last_fetches_port():
    return MockLastFetchesPort()


@pytest.fixture
def ext_int_port():
    return MockExternalIntegrationPort()


@pytest.fixture
def tx_handler():
    return MockTransactionHandlerPort()


@pytest.fixture
def public_key_derivation():
    return MockPublicKeyDerivation()


class TestFetchCryptoDataManualWallets:
    @pytest.mark.asyncio
    async def test_manual_wallet_fetch(
        self,
        position_port,
        crypto_asset_registry,
        crypto_asset_info,
        last_fetches_port,
        ext_int_port,
        tx_handler,
        public_key_derivation,
    ):
        wallet = _make_manual_wallet()
        wallet_port = MockCryptoWalletPort([wallet])
        fetcher = MockCryptoEntityFetcher()

        use_case = FetchCryptoDataImpl(
            position_port,
            {BITCOIN_ENTITY: fetcher},
            wallet_port,
            crypto_asset_registry,
            crypto_asset_info,
            last_fetches_port,
            ext_int_port,
            tx_handler,
            public_key_derivation,
        )

        result = await use_case.execute(
            FetchRequest(entity_id=BITCOIN_ID, features=[Feature.POSITION])
        )

        assert result.code == FetchResultCode.COMPLETED
        assert len(position_port.saved) == 1
        assert wallet_port.inserted_hd_addresses == {}

    @pytest.mark.asyncio
    async def test_manual_wallet_no_hd_addresses_inserted(
        self,
        position_port,
        crypto_asset_registry,
        crypto_asset_info,
        last_fetches_port,
        ext_int_port,
        tx_handler,
        public_key_derivation,
    ):
        wallet = _make_manual_wallet(addresses=["a1", "a2"])
        wallet_port = MockCryptoWalletPort([wallet])
        fetcher = MockCryptoEntityFetcher()

        use_case = FetchCryptoDataImpl(
            position_port,
            {BITCOIN_ENTITY: fetcher},
            wallet_port,
            crypto_asset_registry,
            crypto_asset_info,
            last_fetches_port,
            ext_int_port,
            tx_handler,
            public_key_derivation,
        )

        await use_case.execute(
            FetchRequest(entity_id=BITCOIN_ID, features=[Feature.POSITION])
        )

        assert wallet_port.inserted_hd_addresses == {}


class TestFetchCryptoDataDerivedWallets:
    @pytest.mark.asyncio
    async def test_derived_wallet_first_fetch_no_txs(
        self,
        position_port,
        crypto_asset_registry,
        crypto_asset_info,
        last_fetches_port,
        ext_int_port,
        tx_handler,
        public_key_derivation,
    ):
        wallet = _make_derived_wallet()
        wallet_port = MockCryptoWalletPort([wallet])

        def no_txs_fetcher(request: CryptoFetchRequest):
            results = {}
            for addr in request.addresses:
                results[addr] = CryptoFetchResult(
                    address=addr,
                    has_txs=False,
                    assets=[
                        CryptoFetchedPosition(
                            id=uuid4(),
                            symbol="BTC",
                            balance=Dezimal(0),
                            type=CryptoCurrencyType.NATIVE,
                        )
                    ],
                )
            return CryptoFetchResults(results=results)

        fetcher = MockCryptoEntityFetcher(results_fn=no_txs_fetcher)

        use_case = FetchCryptoDataImpl(
            position_port,
            {BITCOIN_ENTITY: fetcher},
            wallet_port,
            crypto_asset_registry,
            crypto_asset_info,
            last_fetches_port,
            ext_int_port,
            tx_handler,
            public_key_derivation,
        )

        await use_case.execute(
            FetchRequest(entity_id=BITCOIN_ID, features=[Feature.POSITION])
        )

        assert (
            wallet.id not in wallet_port.inserted_hd_addresses
            or wallet_port.inserted_hd_addresses.get(wallet.id) == []
        )

    @pytest.mark.asyncio
    async def test_derived_wallet_discovers_used_addresses(
        self,
        position_port,
        crypto_asset_registry,
        crypto_asset_info,
        last_fetches_port,
        ext_int_port,
        tx_handler,
        public_key_derivation,
    ):
        wallet = _make_derived_wallet()
        wallet_port = MockCryptoWalletPort([wallet])

        used_recv_indices = {0, 1, 2, 3, 4}
        used_change_indices = {0, 1}

        def selective_fetcher(request: CryptoFetchRequest):
            results = {}
            for addr in request.addresses:
                has_txs = False
                if addr.startswith("recv_"):
                    idx = int(addr.split("_")[1])
                    has_txs = idx in used_recv_indices
                elif addr.startswith("change_"):
                    idx = int(addr.split("_")[1])
                    has_txs = idx in used_change_indices

                balance = Dezimal("1.0") if has_txs else Dezimal(0)
                results[addr] = CryptoFetchResult(
                    address=addr,
                    has_txs=has_txs,
                    assets=[
                        CryptoFetchedPosition(
                            id=uuid4(),
                            symbol="BTC",
                            balance=balance,
                            type=CryptoCurrencyType.NATIVE,
                        )
                    ],
                )
            return CryptoFetchResults(results=results)

        fetcher = MockCryptoEntityFetcher(results_fn=selective_fetcher)

        use_case = FetchCryptoDataImpl(
            position_port,
            {BITCOIN_ENTITY: fetcher},
            wallet_port,
            crypto_asset_registry,
            crypto_asset_info,
            last_fetches_port,
            ext_int_port,
            tx_handler,
            public_key_derivation,
        )

        await use_case.execute(
            FetchRequest(entity_id=BITCOIN_ID, features=[Feature.POSITION])
        )

        stored = wallet_port.inserted_hd_addresses.get(wallet.id, [])
        stored_addrs = {a.address for a in stored}

        for i in used_recv_indices:
            assert f"recv_{i}" in stored_addrs
        for i in used_change_indices:
            assert f"change_{i}" in stored_addrs

        assert len(stored) == len(used_recv_indices) + len(used_change_indices)

    @pytest.mark.asyncio
    async def test_derived_wallet_gap_stops_discovery(
        self,
        position_port,
        crypto_asset_registry,
        crypto_asset_info,
        last_fetches_port,
        ext_int_port,
        tx_handler,
        public_key_derivation,
    ):
        wallet = _make_derived_wallet()
        wallet_port = MockCryptoWalletPort([wallet])

        def only_first_used(request: CryptoFetchRequest):
            results = {}
            for addr in request.addresses:
                has_txs = addr == "recv_0"
                results[addr] = CryptoFetchResult(
                    address=addr,
                    has_txs=has_txs,
                    assets=[
                        CryptoFetchedPosition(
                            id=uuid4(),
                            symbol="BTC",
                            balance=Dezimal("1.0") if has_txs else Dezimal(0),
                            type=CryptoCurrencyType.NATIVE,
                        )
                    ],
                )
            return CryptoFetchResults(results=results)

        fetcher = MockCryptoEntityFetcher(results_fn=only_first_used)

        use_case = FetchCryptoDataImpl(
            position_port,
            {BITCOIN_ENTITY: fetcher},
            wallet_port,
            crypto_asset_registry,
            crypto_asset_info,
            last_fetches_port,
            ext_int_port,
            tx_handler,
            public_key_derivation,
        )

        await use_case.execute(
            FetchRequest(entity_id=BITCOIN_ID, features=[Feature.POSITION])
        )

        stored = wallet_port.inserted_hd_addresses.get(wallet.id, [])
        stored_recv = [a for a in stored if a.change == 0]
        assert len(stored_recv) == 1
        assert stored_recv[0].address == "recv_0"

    @pytest.mark.asyncio
    async def test_derived_wallet_with_existing_addresses_continues_from_last(
        self,
        position_port,
        crypto_asset_registry,
        crypto_asset_info,
        last_fetches_port,
        ext_int_port,
        tx_handler,
        public_key_derivation,
    ):
        existing_hd = [
            HDAddress(
                address=f"recv_{i}",
                index=i,
                change=0,
                path=f"m/84'/0'/0'/0/{i}",
                pubkey=f"pub_recv_{i}",
            )
            for i in range(5)
        ]
        wallet = _make_derived_wallet(hd_addresses=existing_hd)
        wallet_port = MockCryptoWalletPort([wallet])

        used_at_5 = True

        def fetcher_fn(request: CryptoFetchRequest):
            results = {}
            for addr in request.addresses:
                has_txs = False
                if addr == "recv_5":
                    has_txs = used_at_5
                elif addr.startswith("recv_"):
                    idx = int(addr.split("_")[1])
                    has_txs = idx < 5
                results[addr] = CryptoFetchResult(
                    address=addr,
                    has_txs=has_txs,
                    assets=[
                        CryptoFetchedPosition(
                            id=uuid4(),
                            symbol="BTC",
                            balance=Dezimal("0.1") if has_txs else Dezimal(0),
                            type=CryptoCurrencyType.NATIVE,
                        )
                    ],
                )
            return CryptoFetchResults(results=results)

        fetcher = MockCryptoEntityFetcher(results_fn=fetcher_fn)

        use_case = FetchCryptoDataImpl(
            position_port,
            {BITCOIN_ENTITY: fetcher},
            wallet_port,
            crypto_asset_registry,
            crypto_asset_info,
            last_fetches_port,
            ext_int_port,
            tx_handler,
            public_key_derivation,
        )

        await use_case.execute(
            FetchRequest(entity_id=BITCOIN_ID, features=[Feature.POSITION])
        )

        stored = wallet_port.inserted_hd_addresses.get(wallet.id, [])
        new_recv = [a for a in stored if a.change == 0]
        assert any(a.address == "recv_5" for a in new_recv)
        assert all(a.index >= 5 for a in new_recv)

    @pytest.mark.asyncio
    async def test_derived_wallet_merges_balances(
        self,
        position_port,
        crypto_asset_registry,
        crypto_asset_info,
        last_fetches_port,
        ext_int_port,
        tx_handler,
        public_key_derivation,
    ):
        existing_hd = [
            HDAddress(
                address="recv_0",
                index=0,
                change=0,
                path="m/84'/0'/0'/0/0",
                pubkey="pub_recv_0",
            ),
            HDAddress(
                address="recv_1",
                index=1,
                change=0,
                path="m/84'/0'/0'/0/1",
                pubkey="pub_recv_1",
            ),
        ]
        wallet = _make_derived_wallet(hd_addresses=existing_hd)
        wallet_port = MockCryptoWalletPort([wallet])

        def fetcher_fn(request: CryptoFetchRequest):
            results = {}
            for addr in request.addresses:
                has_txs = addr in ("recv_0", "recv_1")
                balance = (
                    Dezimal("1.5")
                    if addr == "recv_0"
                    else (Dezimal("0.5") if addr == "recv_1" else Dezimal(0))
                )
                results[addr] = CryptoFetchResult(
                    address=addr,
                    has_txs=has_txs,
                    assets=[
                        CryptoFetchedPosition(
                            id=uuid4(),
                            symbol="BTC",
                            balance=balance,
                            type=CryptoCurrencyType.NATIVE,
                        )
                    ],
                )
            return CryptoFetchResults(results=results)

        fetcher = MockCryptoEntityFetcher(results_fn=fetcher_fn)

        use_case = FetchCryptoDataImpl(
            position_port,
            {BITCOIN_ENTITY: fetcher},
            wallet_port,
            crypto_asset_registry,
            crypto_asset_info,
            last_fetches_port,
            ext_int_port,
            tx_handler,
            public_key_derivation,
        )

        await use_case.execute(
            FetchRequest(entity_id=BITCOIN_ID, features=[Feature.POSITION])
        )

        saved_position = position_port.saved[0]
        crypto_wallets = saved_position.products["CRYPTO"].entries
        target_wallet = next(w for w in crypto_wallets if w.id == wallet.id)
        btc_asset = next(a for a in target_wallet.assets if a.symbol == "BTC")
        assert btc_asset.amount == Dezimal("2.0")


class TestFetchCryptoDataMixed:
    @pytest.mark.asyncio
    async def test_mixed_manual_and_derived_wallets(
        self,
        position_port,
        crypto_asset_registry,
        crypto_asset_info,
        last_fetches_port,
        ext_int_port,
        tx_handler,
        public_key_derivation,
    ):
        manual_wallet = _make_manual_wallet(addresses=["manual_addr"])
        derived_wallet = _make_derived_wallet()
        wallet_port = MockCryptoWalletPort([manual_wallet, derived_wallet])

        def fetcher_fn(request: CryptoFetchRequest):
            results = {}
            for addr in request.addresses:
                has_txs = addr == "manual_addr" or addr == "recv_0"
                balance = Dezimal("1.0") if has_txs else Dezimal(0)
                results[addr] = CryptoFetchResult(
                    address=addr,
                    has_txs=has_txs,
                    assets=[
                        CryptoFetchedPosition(
                            id=uuid4(),
                            symbol="BTC",
                            balance=balance,
                            type=CryptoCurrencyType.NATIVE,
                        )
                    ],
                )
            return CryptoFetchResults(results=results)

        fetcher = MockCryptoEntityFetcher(results_fn=fetcher_fn)

        use_case = FetchCryptoDataImpl(
            position_port,
            {BITCOIN_ENTITY: fetcher},
            wallet_port,
            crypto_asset_registry,
            crypto_asset_info,
            last_fetches_port,
            ext_int_port,
            tx_handler,
            public_key_derivation,
        )

        await use_case.execute(
            FetchRequest(entity_id=BITCOIN_ID, features=[Feature.POSITION])
        )

        assert len(position_port.saved) == 1
        saved = position_port.saved[0]
        crypto_wallets = saved.products["CRYPTO"].entries
        assert len(crypto_wallets) == 2

        assert manual_wallet.id not in wallet_port.inserted_hd_addresses

        derived_stored = wallet_port.inserted_hd_addresses.get(derived_wallet.id, [])
        assert any(a.address == "recv_0" for a in derived_stored)

    @pytest.mark.asyncio
    async def test_single_upfront_fetch_for_manual_and_known_derived(
        self,
        position_port,
        crypto_asset_registry,
        crypto_asset_info,
        last_fetches_port,
        ext_int_port,
        tx_handler,
        public_key_derivation,
    ):
        existing_hd = [
            HDAddress(
                address="recv_0",
                index=0,
                change=0,
                path="m/84'/0'/0'/0/0",
                pubkey="pub_recv_0",
            ),
            HDAddress(
                address="recv_1",
                index=1,
                change=0,
                path="m/84'/0'/0'/0/1",
                pubkey="pub_recv_1",
            ),
        ]
        manual_wallet = _make_manual_wallet(addresses=["manual_addr"])
        derived_wallet = _make_derived_wallet(hd_addresses=existing_hd)
        wallet_port = MockCryptoWalletPort([manual_wallet, derived_wallet])

        def fetcher_fn(request: CryptoFetchRequest):
            results = {}
            for addr in request.addresses:
                has_txs = addr in ("manual_addr", "recv_0", "recv_1")
                results[addr] = CryptoFetchResult(
                    address=addr,
                    has_txs=has_txs,
                    assets=[
                        CryptoFetchedPosition(
                            id=uuid4(),
                            symbol="BTC",
                            balance=Dezimal("1.0") if has_txs else Dezimal(0),
                            type=CryptoCurrencyType.NATIVE,
                        )
                    ],
                )
            return CryptoFetchResults(results=results)

        fetcher = MockCryptoEntityFetcher(results_fn=fetcher_fn)

        use_case = FetchCryptoDataImpl(
            position_port,
            {BITCOIN_ENTITY: fetcher},
            wallet_port,
            crypto_asset_registry,
            crypto_asset_info,
            last_fetches_port,
            ext_int_port,
            tx_handler,
            public_key_derivation,
        )

        await use_case.execute(
            FetchRequest(entity_id=BITCOIN_ID, features=[Feature.POSITION])
        )

        first_call = fetcher.fetch_calls[0]
        assert "manual_addr" in first_call.addresses
        assert "recv_0" in first_call.addresses
        assert "recv_1" in first_call.addresses


class TestDiscoverWalletAddresses:
    @pytest.mark.asyncio
    async def test_stops_after_gap_with_no_txs(
        self,
        position_port,
        crypto_asset_registry,
        crypto_asset_info,
        last_fetches_port,
        ext_int_port,
        tx_handler,
        public_key_derivation,
    ):
        wallet = _make_derived_wallet()

        def no_txs(request: CryptoFetchRequest):
            results = {}
            for addr in request.addresses:
                results[addr] = CryptoFetchResult(
                    address=addr,
                    has_txs=False,
                    assets=[
                        CryptoFetchedPosition(
                            id=uuid4(),
                            symbol="BTC",
                            balance=Dezimal(0),
                            type=CryptoCurrencyType.NATIVE,
                        )
                    ],
                )
            return CryptoFetchResults(results=results)

        fetcher = MockCryptoEntityFetcher(results_fn=no_txs)
        wallet_port = MockCryptoWalletPort([wallet])

        use_case = FetchCryptoDataImpl(
            position_port,
            {BITCOIN_ENTITY: fetcher},
            wallet_port,
            crypto_asset_registry,
            crypto_asset_info,
            last_fetches_port,
            ext_int_port,
            tx_handler,
            public_key_derivation,
        )

        used, results = await use_case._discover_wallet_addresses(
            wallet,
            CoinType.BITCOIN,
            fetcher=fetcher,
            integrations={},
        )

        assert len(used) == 0
        total_fetched = sum(len(c.addresses) for c in fetcher.fetch_calls)
        assert total_fetched <= (UNUSED_GAP + DERIVATION_BATCH_SIZE) * 2

    @pytest.mark.asyncio
    async def test_finds_used_addresses_across_both_chains(
        self,
        position_port,
        crypto_asset_registry,
        crypto_asset_info,
        last_fetches_port,
        ext_int_port,
        tx_handler,
        public_key_derivation,
    ):
        wallet = _make_derived_wallet()
        used_recv = {0, 5, 10, 15, 19}
        used_change = {0, 2}

        def selective(request: CryptoFetchRequest):
            results = {}
            for addr in request.addresses:
                parts = addr.split("_")
                idx = int(parts[1]) if len(parts) == 2 else -1
                has_txs = (addr.startswith("recv_") and idx in used_recv) or (
                    addr.startswith("change_") and idx in used_change
                )
                results[addr] = CryptoFetchResult(
                    address=addr,
                    has_txs=has_txs,
                    assets=[
                        CryptoFetchedPosition(
                            id=uuid4(),
                            symbol="BTC",
                            balance=Dezimal("0.1") if has_txs else Dezimal(0),
                            type=CryptoCurrencyType.NATIVE,
                        )
                    ],
                )
            return CryptoFetchResults(results=results)

        fetcher = MockCryptoEntityFetcher(results_fn=selective)
        wallet_port = MockCryptoWalletPort([wallet])

        use_case = FetchCryptoDataImpl(
            position_port,
            {BITCOIN_ENTITY: fetcher},
            wallet_port,
            crypto_asset_registry,
            crypto_asset_info,
            last_fetches_port,
            ext_int_port,
            tx_handler,
            public_key_derivation,
        )

        used, results = await use_case._discover_wallet_addresses(
            wallet,
            CoinType.BITCOIN,
            fetcher=fetcher,
            integrations={},
        )

        found_addrs = {da.address for da in used}
        for i in used_recv:
            assert f"recv_{i}" in found_addrs
        for i in used_change:
            assert f"change_{i}" in found_addrs

    @pytest.mark.asyncio
    async def test_combined_fetch_sends_both_chains_together(
        self,
        position_port,
        crypto_asset_registry,
        crypto_asset_info,
        last_fetches_port,
        ext_int_port,
        tx_handler,
        public_key_derivation,
    ):
        wallet = _make_derived_wallet()

        def no_txs(request: CryptoFetchRequest):
            results = {}
            for addr in request.addresses:
                results[addr] = CryptoFetchResult(
                    address=addr,
                    has_txs=False,
                    assets=[
                        CryptoFetchedPosition(
                            id=uuid4(),
                            symbol="BTC",
                            balance=Dezimal(0),
                            type=CryptoCurrencyType.NATIVE,
                        )
                    ],
                )
            return CryptoFetchResults(results=results)

        fetcher = MockCryptoEntityFetcher(results_fn=no_txs)
        wallet_port = MockCryptoWalletPort([wallet])

        use_case = FetchCryptoDataImpl(
            position_port,
            {BITCOIN_ENTITY: fetcher},
            wallet_port,
            crypto_asset_registry,
            crypto_asset_info,
            last_fetches_port,
            ext_int_port,
            tx_handler,
            public_key_derivation,
        )

        await use_case._discover_wallet_addresses(
            wallet,
            CoinType.BITCOIN,
            fetcher=fetcher,
            integrations={},
        )

        for call in fetcher.fetch_calls:
            has_recv = any(a.startswith("recv_") for a in call.addresses)
            has_change = any(a.startswith("change_") for a in call.addresses)
            assert has_recv and has_change

    @pytest.mark.asyncio
    async def test_returns_accumulated_fetch_results(
        self,
        position_port,
        crypto_asset_registry,
        crypto_asset_info,
        last_fetches_port,
        ext_int_port,
        tx_handler,
        public_key_derivation,
    ):
        wallet = _make_derived_wallet()

        def fetcher_fn(request: CryptoFetchRequest):
            results = {}
            for addr in request.addresses:
                has_txs = addr == "recv_0"
                results[addr] = CryptoFetchResult(
                    address=addr,
                    has_txs=has_txs,
                    assets=[
                        CryptoFetchedPosition(
                            id=uuid4(),
                            symbol="BTC",
                            balance=Dezimal("1.5") if has_txs else Dezimal(0),
                            type=CryptoCurrencyType.NATIVE,
                        )
                    ],
                )
            return CryptoFetchResults(results=results)

        fetcher = MockCryptoEntityFetcher(results_fn=fetcher_fn)
        wallet_port = MockCryptoWalletPort([wallet])

        use_case = FetchCryptoDataImpl(
            position_port,
            {BITCOIN_ENTITY: fetcher},
            wallet_port,
            crypto_asset_registry,
            crypto_asset_info,
            last_fetches_port,
            ext_int_port,
            tx_handler,
            public_key_derivation,
        )

        used, results = await use_case._discover_wallet_addresses(
            wallet,
            CoinType.BITCOIN,
            fetcher=fetcher,
            integrations={},
        )

        assert "recv_0" in results
        assert results["recv_0"].assets[0].balance == Dezimal("1.5")


class TestProcessDiscoveryBatch:
    def test_all_used_resets_gap(self):
        batch = [
            DerivedAddress(
                index=i, path=f"m/0/{i}", address=f"a_{i}", pubkey=f"p_{i}", change=0
            )
            for i in range(5)
        ]
        fetch_results = {
            f"a_{i}": CryptoFetchResult(
                address=f"a_{i}",
                has_txs=True,
                assets=[
                    CryptoFetchedPosition(
                        id=uuid4(),
                        symbol="BTC",
                        balance=Dezimal("0.1"),
                        type=CryptoCurrencyType.NATIVE,
                    )
                ],
            )
            for i in range(5)
        }
        gap, used = FetchCryptoDataImpl._process_discovery_batch(
            batch, fetch_results, 0
        )
        assert gap == 0
        assert len(used) == 5

    def test_no_used_increments_gap(self):
        batch = [
            DerivedAddress(
                index=i, path=f"m/0/{i}", address=f"a_{i}", pubkey=f"p_{i}", change=0
            )
            for i in range(5)
        ]
        fetch_results = {
            f"a_{i}": CryptoFetchResult(
                address=f"a_{i}",
                has_txs=False,
                assets=[
                    CryptoFetchedPosition(
                        id=uuid4(),
                        symbol="BTC",
                        balance=Dezimal(0),
                        type=CryptoCurrencyType.NATIVE,
                    )
                ],
            )
            for i in range(5)
        }
        gap, used = FetchCryptoDataImpl._process_discovery_batch(
            batch, fetch_results, 0
        )
        assert gap == 5
        assert len(used) == 0

    def test_stops_at_gap_threshold(self):
        batch = [
            DerivedAddress(
                index=i, path=f"m/0/{i}", address=f"a_{i}", pubkey=f"p_{i}", change=0
            )
            for i in range(UNUSED_GAP + 5)
        ]
        fetch_results = {
            f"a_{i}": CryptoFetchResult(
                address=f"a_{i}",
                has_txs=False,
                assets=[
                    CryptoFetchedPosition(
                        id=uuid4(),
                        symbol="BTC",
                        balance=Dezimal(0),
                        type=CryptoCurrencyType.NATIVE,
                    )
                ],
            )
            for i in range(UNUSED_GAP + 5)
        }
        gap, used = FetchCryptoDataImpl._process_discovery_batch(
            batch, fetch_results, 0
        )
        assert gap == UNUSED_GAP
        assert len(used) == 0


class TestMapDerivedToHDAddresses:
    def test_mapping(self):
        derived = [
            DerivedAddress(
                index=0,
                path="m/84'/0'/0'/0/0",
                address="addr_0",
                pubkey="pub_0",
                change=0,
            ),
            DerivedAddress(
                index=1,
                path="m/84'/0'/0'/1/1",
                address="addr_1",
                pubkey="pub_1",
                change=1,
            ),
        ]
        result = FetchCryptoDataImpl._map_derived_to_hd_addresses(derived)

        assert len(result) == 2
        assert result[0].address == "addr_0"
        assert result[0].index == 0
        assert result[0].change == 0
        assert result[0].path == "m/84'/0'/0'/0/0"
        assert result[0].pubkey == "pub_0"
        assert result[1].address == "addr_1"
        assert result[1].change == 1


class TestMergeAddressAssets:
    def test_merge_same_native(self):
        r1 = CryptoFetchResult(
            address="a1",
            assets=[
                CryptoFetchedPosition(
                    id=uuid4(),
                    symbol="BTC",
                    balance=Dezimal("1.0"),
                    type=CryptoCurrencyType.NATIVE,
                )
            ],
        )
        r2 = CryptoFetchResult(
            address="a2",
            assets=[
                CryptoFetchedPosition(
                    id=uuid4(),
                    symbol="BTC",
                    balance=Dezimal("2.0"),
                    type=CryptoCurrencyType.NATIVE,
                )
            ],
        )
        merged = FetchCryptoDataImpl._merge_address_assets([r1, r2])
        assert len(merged) == 1
        assert merged[0].amount == Dezimal("3.0")

    def test_merge_token_by_contract(self):
        r1 = CryptoFetchResult(
            address="a1",
            assets=[
                CryptoFetchedPosition(
                    id=uuid4(),
                    symbol="USDT",
                    balance=Dezimal("100"),
                    type=CryptoCurrencyType.TOKEN,
                    contract_address="0xdac17",
                )
            ],
        )
        r2 = CryptoFetchResult(
            address="a2",
            assets=[
                CryptoFetchedPosition(
                    id=uuid4(),
                    symbol="USDT",
                    balance=Dezimal("50"),
                    type=CryptoCurrencyType.TOKEN,
                    contract_address="0xDAC17",
                )
            ],
        )
        merged = FetchCryptoDataImpl._merge_address_assets([r1, r2])
        assert len(merged) == 1
        assert merged[0].amount == Dezimal("150")
