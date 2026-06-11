from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from application.use_cases.get_exchange_rates import GetExchangeRatesImpl
from domain.crypto import CryptoCurrencyType
from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.global_position import (
    CryptoCurrencies,
    CryptoCurrencyPosition,
    CryptoCurrencyWallet,
    GlobalPosition,
    ProductType,
)


def _make_entity():
    return Entity(
        id=uuid4(),
        name="Test",
        natural_id="test",
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.NATIVE,
        icon_url=None,
    )


def _make_crypto_position(symbol, contract_address=None):
    return CryptoCurrencyPosition(
        id=uuid4(),
        symbol=symbol,
        amount=Dezimal("1"),
        type=CryptoCurrencyType.NATIVE,
        contract_address=contract_address,
    )


def _make_token_position(symbol, contract_address):
    return CryptoCurrencyPosition(
        id=uuid4(),
        symbol=symbol,
        amount=Dezimal("1"),
        type=CryptoCurrencyType.TOKEN,
        contract_address=contract_address,
    )


async def _run_jobs_sequentially(jobs, timeout):
    outcomes = []
    for job_factory, meta in jobs:
        try:
            result = await job_factory()
            outcomes.append((meta[0], meta[1], result, None))
        except Exception as e:
            outcomes.append((meta[0], meta[1], None, e))
    return outcomes


def _build_use_case(
    exchange_rates_provider=None,
    crypto_asset_info_provider=None,
    metal_price_provider=None,
    exchange_rates_storage=None,
    position_port=None,
    job_scheduler=None,
):
    if exchange_rates_provider is None:
        exchange_rates_provider = AsyncMock()
        exchange_rates_provider.get_matrix = AsyncMock(return_value={})
    if crypto_asset_info_provider is None:
        crypto_asset_info_provider = AsyncMock()
    if metal_price_provider is None:
        metal_price_provider = AsyncMock()
    if exchange_rates_storage is None:
        exchange_rates_storage = AsyncMock()
        exchange_rates_storage.get = AsyncMock(return_value=None)
        exchange_rates_storage.get_last_saved = AsyncMock(return_value=None)
        exchange_rates_storage.save = AsyncMock()
    if position_port is None:
        position_port = AsyncMock()

    return GetExchangeRatesImpl(
        exchange_rates_provider=exchange_rates_provider,
        crypto_asset_info_provider=crypto_asset_info_provider,
        metal_price_provider=metal_price_provider,
        exchange_rates_storage=exchange_rates_storage,
        position_port=position_port,
        job_scheduler=job_scheduler,
    )


class TestIgnoredCryptoSymbols:
    @pytest.mark.asyncio
    async def test_ignored_symbol_is_not_sent_to_crypto_provider(self):
        entity = _make_entity()
        wallet = CryptoCurrencyWallet(
            id=uuid4(),
            assets=[
                _make_crypto_position("BTC"),
                _make_crypto_position("BNFCR"),
            ],
        )
        gp = GlobalPosition(
            id=uuid4(),
            entity=entity,
            products={ProductType.CRYPTO: CryptoCurrencies(entries=[wallet])},
        )

        position_port = AsyncMock()
        position_port.get_last_grouped_by_entity = AsyncMock(return_value={entity: gp})

        crypto_provider = AsyncMock()
        crypto_provider.get_multiple_prices_by_symbol = AsyncMock(
            return_value={"BTC": {"EUR": Dezimal("50000")}}
        )

        captured_jobs = []

        async def fake_scheduler(jobs, timeout):
            captured_jobs.extend(jobs)
            outcomes = []
            for job_factory, meta in jobs:
                try:
                    result = await job_factory()
                    outcomes.append((meta[0], meta[1], result, None))
                except Exception as e:
                    outcomes.append((meta[0], meta[1], None, e))
            return outcomes

        uc = _build_use_case(
            position_port=position_port,
            crypto_asset_info_provider=crypto_provider,
            job_scheduler=fake_scheduler,
        )

        await uc.execute(initial_load=False)

        crypto_provider.get_multiple_prices_by_symbol.assert_called_once()
        symbols_arg = crypto_provider.get_multiple_prices_by_symbol.call_args[0][0]
        assert "BNFCR" not in symbols_arg
        assert "BTC" in symbols_arg

    @pytest.mark.asyncio
    async def test_only_ignored_symbols_results_in_no_crypto_fetch(self):
        entity = _make_entity()
        wallet = CryptoCurrencyWallet(
            id=uuid4(),
            assets=[_make_crypto_position("BNFCR")],
        )
        gp = GlobalPosition(
            id=uuid4(),
            entity=entity,
            products={ProductType.CRYPTO: CryptoCurrencies(entries=[wallet])},
        )

        position_port = AsyncMock()
        position_port.get_last_grouped_by_entity = AsyncMock(return_value={entity: gp})

        crypto_provider = AsyncMock()

        captured_jobs = []

        async def fake_scheduler(jobs, timeout):
            captured_jobs.extend(jobs)
            outcomes = []
            for job_factory, meta in jobs:
                try:
                    result = await job_factory()
                    outcomes.append((meta[0], meta[1], result, None))
                except Exception as e:
                    outcomes.append((meta[0], meta[1], None, e))
            return outcomes

        uc = _build_use_case(
            position_port=position_port,
            crypto_asset_info_provider=crypto_provider,
            job_scheduler=fake_scheduler,
        )

        await uc.execute(initial_load=False)

        crypto_provider.get_multiple_prices_by_symbol.assert_not_called()
        crypto_provider.get_prices_by_addresses.assert_not_called()

        crypto_jobs = [
            j for j in captured_jobs if j[1][0] in ("crypto", "crypto_batch")
        ]
        assert len(crypto_jobs) == 0


class TestCryptoRateKeying:
    @pytest.mark.asyncio
    async def test_native_coin_keyed_by_symbol(self):
        entity = _make_entity()
        wallet = CryptoCurrencyWallet(
            id=uuid4(),
            assets=[_make_crypto_position("BTC")],
        )
        gp = GlobalPosition(
            id=uuid4(),
            entity=entity,
            products={ProductType.CRYPTO: CryptoCurrencies(entries=[wallet])},
        )

        position_port = AsyncMock()
        position_port.get_last_grouped_by_entity = AsyncMock(return_value={entity: gp})

        crypto_provider = AsyncMock()
        crypto_provider.get_multiple_prices_by_symbol = AsyncMock(
            return_value={"BTC": {"EUR": Dezimal("50000")}}
        )
        crypto_provider.get_prices_by_addresses = AsyncMock(return_value={})

        uc = _build_use_case(
            position_port=position_port,
            crypto_asset_info_provider=crypto_provider,
            job_scheduler=_run_jobs_sequentially,
        )

        matrix = await uc.execute(initial_load=False)

        crypto_provider.get_prices_by_addresses.assert_not_called()
        symbols_arg = crypto_provider.get_multiple_prices_by_symbol.call_args[0][0]
        assert "BTC" in symbols_arg
        assert matrix["EUR"]["BTC"] == Dezimal(1) / Dezimal("50000")

    @pytest.mark.asyncio
    async def test_token_keyed_by_contract_address(self):
        entity = _make_entity()
        wallet = CryptoCurrencyWallet(
            id=uuid4(),
            assets=[_make_token_position("BTCB", "0xAbC123")],
        )
        gp = GlobalPosition(
            id=uuid4(),
            entity=entity,
            products={ProductType.CRYPTO: CryptoCurrencies(entries=[wallet])},
        )

        position_port = AsyncMock()
        position_port.get_last_grouped_by_entity = AsyncMock(return_value={entity: gp})

        crypto_provider = AsyncMock()
        crypto_provider.get_multiple_prices_by_symbol = AsyncMock(return_value={})
        crypto_provider.get_prices_by_addresses = AsyncMock(
            return_value={"0xabc123": {"EUR": Dezimal("50000")}}
        )

        uc = _build_use_case(
            position_port=position_port,
            crypto_asset_info_provider=crypto_provider,
            job_scheduler=_run_jobs_sequentially,
        )

        matrix = await uc.execute(initial_load=False)

        crypto_provider.get_multiple_prices_by_symbol.assert_not_called()
        addresses_arg = crypto_provider.get_prices_by_addresses.call_args[0][0]
        assert addresses_arg == ["0xabc123"]
        assert matrix["EUR"]["0xabc123"] == Dezimal(1) / Dezimal("50000")
        assert "BTCB" not in matrix["EUR"]

    @pytest.mark.asyncio
    async def test_two_tokens_same_symbol_do_not_collide(self):
        entity = _make_entity()
        wallet = CryptoCurrencyWallet(
            id=uuid4(),
            assets=[
                _make_token_position("BTCB", "0xAAA"),
                _make_token_position("BTCB", "0xBBB"),
            ],
        )
        gp = GlobalPosition(
            id=uuid4(),
            entity=entity,
            products={ProductType.CRYPTO: CryptoCurrencies(entries=[wallet])},
        )

        position_port = AsyncMock()
        position_port.get_last_grouped_by_entity = AsyncMock(return_value={entity: gp})

        crypto_provider = AsyncMock()
        crypto_provider.get_multiple_prices_by_symbol = AsyncMock(return_value={})
        crypto_provider.get_prices_by_addresses = AsyncMock(
            return_value={
                "0xaaa": {"EUR": Dezimal("50000")},
                "0xbbb": {"EUR": Dezimal("0.06")},
            }
        )

        uc = _build_use_case(
            position_port=position_port,
            crypto_asset_info_provider=crypto_provider,
            job_scheduler=_run_jobs_sequentially,
        )

        matrix = await uc.execute(initial_load=False)

        addresses_arg = crypto_provider.get_prices_by_addresses.call_args[0][0]
        assert set(addresses_arg) == {"0xaaa", "0xbbb"}
        assert matrix["EUR"]["0xaaa"] == Dezimal(1) / Dezimal("50000")
        assert matrix["EUR"]["0xbbb"] == Dezimal(1) / Dezimal("0.06")

    @pytest.mark.asyncio
    async def test_native_and_token_priced_separately(self):
        entity = _make_entity()
        wallet = CryptoCurrencyWallet(
            id=uuid4(),
            assets=[
                _make_crypto_position("BTC"),
                _make_token_position("BTCB", "0xAAA"),
            ],
        )
        gp = GlobalPosition(
            id=uuid4(),
            entity=entity,
            products={ProductType.CRYPTO: CryptoCurrencies(entries=[wallet])},
        )

        position_port = AsyncMock()
        position_port.get_last_grouped_by_entity = AsyncMock(return_value={entity: gp})

        crypto_provider = AsyncMock()
        crypto_provider.get_multiple_prices_by_symbol = AsyncMock(
            return_value={"BTC": {"EUR": Dezimal("50000")}}
        )
        crypto_provider.get_prices_by_addresses = AsyncMock(
            return_value={"0xaaa": {"EUR": Dezimal("0.06")}}
        )

        uc = _build_use_case(
            position_port=position_port,
            crypto_asset_info_provider=crypto_provider,
            job_scheduler=_run_jobs_sequentially,
        )

        matrix = await uc.execute(initial_load=False)

        symbols_arg = crypto_provider.get_multiple_prices_by_symbol.call_args[0][0]
        addresses_arg = crypto_provider.get_prices_by_addresses.call_args[0][0]
        assert symbols_arg == ["BTC"]
        assert addresses_arg == ["0xaaa"]
        assert matrix["EUR"]["BTC"] == Dezimal(1) / Dezimal("50000")
        assert matrix["EUR"]["0xaaa"] == Dezimal(1) / Dezimal("0.06")
