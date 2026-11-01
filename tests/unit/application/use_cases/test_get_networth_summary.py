from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from application.use_cases.get_networth_summary import GetNetworthSummaryImpl
from domain.commodity import CommodityType, WeightUnit
from domain.crypto import CryptoCurrencyType
from domain.dezimal import Dezimal
from domain.global_position import CardType, ProductType
from domain.networth_summary import NetworthSummaryQuery
from domain.real_estate import RealEstateFlowSubtype


def _d(value):
    return Dezimal(value)


def _entries(*items):
    return SimpleNamespace(entries=list(items))


def _position(products):
    return SimpleNamespace(products=products)


def _crypto_asset(
    symbol,
    amount,
    crypto_asset=True,
    market_value=None,
    currency=None,
    token_address=None,
):
    return SimpleNamespace(
        symbol=symbol,
        amount=_d(amount),
        type=CryptoCurrencyType.TOKEN if token_address else CryptoCurrencyType.NATIVE,
        contract_address=token_address,
        crypto_asset=SimpleNamespace() if crypto_asset else None,
        market_value=_d(market_value) if market_value is not None else None,
        currency=currency,
    )


def _real_estate(market, loans=(), currency="EUR", is_residence=False):
    flows = [
        SimpleNamespace(
            flow_subtype=RealEstateFlowSubtype.LOAN,
            payload=SimpleNamespace(principal_outstanding=_d(outstanding)),
            linked_loan_hash=loan_hash,
        )
        for loan_hash, outstanding in loans
    ]
    return SimpleNamespace(
        basic_info=SimpleNamespace(is_residence=is_residence),
        valuation_info=SimpleNamespace(estimated_market_value=_d(market)),
        flows=flows,
        currency=currency,
    )


def _build(positions, real_estate=None, rates=None, disabled=None, loans=None):
    position_port = AsyncMock()
    position_port.get_last_by_entity_broken_down = AsyncMock(
        return_value={uuid4(): positions}
    )
    position_port.get_loans_by_hash = AsyncMock(return_value=loans or {})
    entity_port = AsyncMock()
    entity_port.get_disabled_entities = AsyncMock(return_value=disabled or [])
    real_estate_port = AsyncMock()
    real_estate_port.get_all = AsyncMock(return_value=real_estate or [])
    exchange_rate_storage = AsyncMock()
    exchange_rate_storage.get = AsyncMock(return_value=rates or {})
    uc = GetNetworthSummaryImpl(
        position_port, entity_port, real_estate_port, exchange_rate_storage
    )
    return uc, position_port


@pytest.mark.asyncio
async def test_sums_assets_and_converts_currencies():
    rates = {"EUR": {"USD": _d("2")}}
    positions = [
        _position(
            {
                ProductType.ACCOUNT: _entries(
                    SimpleNamespace(total=_d(100), currency="EUR"),
                    SimpleNamespace(total=_d(50), currency="USD"),
                ),
                ProductType.FUND: _entries(
                    SimpleNamespace(market_value=_d(200), currency="EUR")
                ),
                ProductType.STOCK_ETF: _entries(
                    SimpleNamespace(market_value=_d(40), currency="USD")
                ),
                ProductType.DEPOSIT: _entries(
                    SimpleNamespace(amount=_d(300), currency="EUR")
                ),
                ProductType.FACTORING: _entries(
                    SimpleNamespace(amount=_d(10), currency="EUR")
                ),
                ProductType.REAL_ESTATE_CF: _entries(
                    SimpleNamespace(pending_amount=_d(15), currency="EUR")
                ),
                ProductType.CROWDLENDING: SimpleNamespace(total=_d(25), currency="EUR"),
            }
        )
    ]
    uc, _ = _build(positions, rates=rates)

    result = await uc.execute(NetworthSummaryQuery(base_currency="EUR"))

    assert result.currency == "EUR"
    assert result.breakdown == {
        "ACCOUNT": _d(125),
        "FUND": _d(200),
        "STOCK_ETF": _d(20),
        "DEPOSIT": _d(300),
        "FACTORING": _d(10),
        "REAL_ESTATE_CF": _d(15),
        "CROWDLENDING": _d(25),
    }
    assert result.total == _d(695)
    assert isinstance(result.date, date)


@pytest.mark.asyncio
async def test_excludes_disabled_entities_from_query():
    disabled = SimpleNamespace(id=uuid4())
    uc, position_port = _build([], disabled=[disabled])

    await uc.execute(NetworthSummaryQuery(base_currency="EUR"))

    query = position_port.get_last_by_entity_broken_down.call_args.args[0]
    assert query.excluded_entities == [disabled.id]


@pytest.mark.asyncio
async def test_crypto_live_valuation_and_fallbacks():
    rates = {
        "EUR": {
            "BTC": _d("0.00002"),
            "0xabc": _d("0.5"),
            "USD": _d("2"),
        }
    }
    wallet = SimpleNamespace(
        assets=[
            _crypto_asset("BTC", "0.5"),
            _crypto_asset("TKN", "3", token_address="0xABC"),
            _crypto_asset(
                "ZRN", "1", crypto_asset=False, market_value=80, currency="USD"
            ),
            _crypto_asset("NOPRICE", "4", market_value=12, currency="EUR"),
            _crypto_asset("UNKNOWN", "9", crypto_asset=False),
        ]
    )
    positions = [_position({ProductType.CRYPTO: _entries(wallet)})]
    uc, _ = _build(positions, rates=rates)

    result = await uc.execute(NetworthSummaryQuery(base_currency="EUR"))

    assert result.breakdown == {"CRYPTO": _d(25000 + 6 + 40 + 12)}


@pytest.mark.asyncio
async def test_crypto_market_value_requires_exact_currency_or_rate_entry():
    rates = {"USD": {"EUR": _d("0.5")}}
    wallet = SimpleNamespace(
        assets=[
            _crypto_asset("A", "1", crypto_asset=False, market_value=7, currency=None),
            _crypto_asset(
                "B", "1", crypto_asset=False, market_value=5, currency="PUSD"
            ),
            _crypto_asset("C", "1", crypto_asset=False, market_value=3, currency="EUR"),
        ]
    )
    positions = [_position({ProductType.CRYPTO: _entries(wallet)})]
    uc, _ = _build(positions, rates=rates)

    result = await uc.execute(NetworthSummaryQuery(base_currency="USD"))

    assert result.breakdown == {"CRYPTO": _d(7 + 6)}


@pytest.mark.asyncio
async def test_commodity_uses_live_price_with_raw_amount_fallback():
    rates = {"EUR": {"XAU": _d("0.0005"), "XPT": _d("0.001")}}
    positions = [
        _position(
            {
                ProductType.COMMODITY: _entries(
                    SimpleNamespace(
                        type=CommodityType.GOLD,
                        amount=_d(2),
                        unit=WeightUnit.TROY_OUNCE,
                        market_value=_d(1),
                        currency="EUR",
                    ),
                    SimpleNamespace(
                        type=CommodityType.SILVER,
                        amount=_d(10),
                        unit=WeightUnit.TROY_OUNCE,
                        market_value=_d(300),
                        currency="EUR",
                    ),
                    SimpleNamespace(
                        type=CommodityType.PLATINUM,
                        amount=_d(100),
                        unit=WeightUnit.GRAM,
                        market_value=None,
                        currency=None,
                    ),
                )
            }
        )
    ]
    uc, _ = _build(positions, rates=rates)

    result = await uc.execute(NetworthSummaryQuery(base_currency="EUR"))

    grams_value = _d(100) * _d("0.032150746568628") / _d("0.001")
    assert result.breakdown == {"COMMODITY": _d(4000) + _d(10) + grams_value}


@pytest.mark.asyncio
async def test_derivatives_bucket_by_underlying_and_aliases_stablecoins():
    rates = {"EUR": {"USD": _d("2")}}
    positions = [
        _position(
            {
                ProductType.DERIVATIVE: _entries(
                    SimpleNamespace(
                        underlying_asset=ProductType.STOCK_ETF,
                        market_value=_d(100),
                        currency="EUR",
                    ),
                    SimpleNamespace(
                        underlying_asset=ProductType.CRYPTO,
                        market_value=_d(50),
                        currency="BNFCR",
                    ),
                ),
                ProductType.MARKET_FORECAST: _entries(
                    SimpleNamespace(market_value=_d(20), currency="PUSD")
                ),
            }
        )
    ]
    uc, _ = _build(positions, rates=rates)

    result = await uc.execute(NetworthSummaryQuery(base_currency="EUR"))

    assert result.breakdown == {
        "STOCK_ETF": _d(100),
        "CRYPTO": _d(25),
        "MARKET_FORECAST": _d(10),
    }


@pytest.mark.asyncio
async def test_debts_and_real_estate_equity():
    positions = [
        _position(
            {
                ProductType.CARD: _entries(
                    SimpleNamespace(type=CardType.CREDIT, used=_d(30), currency="EUR"),
                    SimpleNamespace(type=CardType.DEBIT, used=_d(99), currency="EUR"),
                ),
                ProductType.CREDIT: _entries(
                    SimpleNamespace(drawn_amount=_d(40), currency="EUR")
                ),
                ProductType.LOAN: _entries(
                    SimpleNamespace(
                        hash="linked", principal_outstanding=_d(1000), currency="EUR"
                    ),
                    SimpleNamespace(
                        hash="free", principal_outstanding=_d(200), currency="EUR"
                    ),
                ),
            }
        )
    ]
    real_estate = [
        _real_estate(5000, loans=[("linked", 1000)]),
        _real_estate(3000, is_residence=True),
        _real_estate(100, loans=[(None, 500)]),
    ]
    uc, _ = _build(positions, real_estate=real_estate)

    result = await uc.execute(NetworthSummaryQuery(base_currency="EUR"))

    assert result.breakdown == {
        "CARD": _d(-30),
        "CREDIT": _d(-40),
        "LOAN": _d(-200),
        "REAL_ESTATE": _d(4000),
        "REAL_ESTATE_RESIDENCE": _d(3000),
    }
    assert result.total == _d(6730)


@pytest.mark.asyncio
async def test_real_estate_equity_uses_current_linked_loan_outstanding():
    positions = [
        _position(
            {
                ProductType.LOAN: _entries(
                    SimpleNamespace(
                        hash="linked", principal_outstanding=_d(800), currency="EUR"
                    )
                )
            }
        )
    ]
    real_estate = [_real_estate(5000, loans=[("linked", 1000), ("gone", 300)])]
    loans = {"linked": SimpleNamespace(principal_outstanding=_d(800))}
    uc, position_port = _build(positions, real_estate=real_estate, loans=loans)

    result = await uc.execute(NetworthSummaryQuery(base_currency="EUR"))

    hashes = position_port.get_loans_by_hash.call_args.args[0]
    assert sorted(hashes) == ["gone", "linked"]
    assert result.breakdown == {"REAL_ESTATE": _d(3900)}
    assert result.total == _d(3900)


@pytest.mark.asyncio
async def test_keeps_zero_buckets_like_frontend_distribution():
    positions = [
        _position(
            {
                ProductType.ACCOUNT: _entries(
                    SimpleNamespace(total=_d(100), currency="EUR"),
                    SimpleNamespace(total=_d(-100), currency="EUR"),
                ),
                ProductType.FUND: _entries(
                    SimpleNamespace(market_value=_d(0), currency="EUR")
                ),
                ProductType.CROWDLENDING: SimpleNamespace(total=_d(0), currency="EUR"),
                ProductType.CRYPTO: _entries(
                    SimpleNamespace(
                        assets=[_crypto_asset("UNKNOWN", "9", crypto_asset=False)]
                    )
                ),
                ProductType.CARD: _entries(
                    SimpleNamespace(type=CardType.CREDIT, used=_d(0), currency="EUR")
                ),
            }
        )
    ]
    real_estate = [_real_estate(100, loans=[(None, 500)])]
    uc, _ = _build(positions, real_estate=real_estate)

    result = await uc.execute(NetworthSummaryQuery(base_currency="EUR"))

    assert result.breakdown == {"FUND": _d(0), "CRYPTO": _d(0)}
    assert result.total == _d(0)


@pytest.mark.asyncio
async def test_missing_rate_skips_value():
    positions = [
        _position(
            {
                ProductType.ACCOUNT: _entries(
                    SimpleNamespace(total=_d(100), currency="JPY"),
                    SimpleNamespace(total=_d(10), currency="EUR"),
                )
            }
        )
    ]
    uc, _ = _build(positions, rates={})

    result = await uc.execute(NetworthSummaryQuery(base_currency="EUR"))

    assert result.breakdown == {"ACCOUNT": _d(10)}
    assert result.total == _d(10)
