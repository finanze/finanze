from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from application.ports.gains_timeline_port import GainsTimelinePort
from application.use_cases.get_gains_timeline import GetGainsTimelineImpl
from domain.commodity import COMMODITY_HISTORIC_CUTOFF, CommodityType, WeightUnit
from domain.dezimal import Dezimal
from domain.exchange_rate import HistoricMetalRates
from domain.gains_timeline import (
    AssetSnapshot,
    AssetValuation,
    FixedIncomeAccrual,
    GainsAssetFilter,
    GainsBasis,
    GainsBasisStatus,
    GainsCalculationMode,
    GainsFlow,
    GainsMethod,
    GainsQuality,
    GainsSettlement,
    GainsTimelineQuery,
)
from domain.global_position import EquityType, ProductType
from domain.instrument import InstrumentType
from domain.transactions import TxType


def _valuation(quantity, market_value, cost_basis=None):
    return AssetValuation(
        product_type=ProductType.CRYPTO,
        asset_key="BTC",
        currency="EUR",
        quantity=Dezimal(quantity),
        market_value=Dezimal(market_value),
        cost_basis=Dezimal(cost_basis) if cost_basis is not None else None,
    )


def _snapshot(day, quantity, market_value, cost_basis=None):
    return AssetSnapshot(
        holder="wallet",
        moment=datetime(day.year, day.month, day.day, 12),
        valuations=[_valuation(quantity, market_value, cost_basis)],
    )


def _flow(day, transaction_type, amount, quantity=None, fees="0"):
    return GainsFlow(
        holder="wallet",
        product_type=ProductType.CRYPTO,
        asset_key="BTC",
        moment=datetime(day.year, day.month, day.day, 12),
        amount=Dezimal(amount),
        currency="EUR",
        quantity=Dezimal(quantity) if quantity is not None else None,
        fees=Dezimal(fees),
        transaction_type=transaction_type,
    )


def _build(snapshots, flows=None, rates=None, settlements=None, metal=None):
    port = AsyncMock(spec=GainsTimelinePort)
    port.get_data_version.return_value = "1"
    port.get_asset_snapshots.return_value = snapshots
    port.get_flows.return_value = flows or []
    port.get_settlements.return_value = settlements or []

    exchange = AsyncMock()
    exchange.get.return_value = rates or {}

    entity = AsyncMock()
    entity.get_disabled_entities.return_value = []
    entity.get_all.return_value = []

    if metal is None:
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None

    return GetGainsTimelineImpl(port, exchange, entity, metal), port


def _query():
    return GainsTimelineQuery(
        assets=[GainsAssetFilter(product_type=ProductType.CRYPTO)],
        entities=[uuid4()],
    )


class TestGetGainsTimeline:
    def test_allows_wallet_filters_for_crypto(self):
        wallet_id = uuid4()

        asset_filter = GainsAssetFilter(
            product_type=ProductType.CRYPTO,
            wallet_ids=[wallet_id],
        )

        assert asset_filter.wallet_ids == [wallet_id]

    def test_rejects_wallet_filters_for_non_crypto_products(self):
        with pytest.raises(
            ValueError, match="Wallet filters are only supported for crypto"
        ):
            GainsAssetFilter(
                product_type=ProductType.FUND,
                wallet_ids=[uuid4()],
            )

    @pytest.mark.asyncio
    async def test_retains_same_market_asset_in_multiple_currencies(self):
        day = date(2025, 1, 1)
        use_case, _ = _build(
            [
                AssetSnapshot(
                    holder="broker",
                    moment=datetime(2025, 1, 1, 12),
                    valuations=[
                        AssetValuation(
                            product_type=ProductType.FUND,
                            asset_key="IE00TEST0001",
                            currency="EUR",
                            market_value=Dezimal(100),
                            quantity=Dezimal(1),
                            cost_basis=Dezimal(100),
                        ),
                        AssetValuation(
                            product_type=ProductType.FUND,
                            asset_key="IE00TEST0001",
                            currency="USD",
                            market_value=Dezimal(110),
                            quantity=Dezimal(1),
                            cost_basis=Dezimal(110),
                        ),
                    ],
                )
            ],
            rates={"EUR": {"USD": Dezimal("1.1")}},
        )
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.FUND)],
            entities=[uuid4()],
        )

        result = await use_case.execute(query)

        assert result.points[0].date == day
        assert result.points[0].metrics.value == Dezimal(200)

    @pytest.mark.asyncio
    async def test_filters_values_and_flows_by_fund_portfolio_and_equity_type(self):
        moment = datetime(2025, 1, 1, 12)
        use_case, _ = _build(
            [
                AssetSnapshot(
                    holder="broker",
                    moment=moment,
                    valuations=[
                        AssetValuation(
                            product_type=ProductType.FUND,
                            asset_key="IE00RETIREMENT",
                            currency="EUR",
                            market_value=Dezimal(100),
                            quantity=Dezimal(1),
                            portfolio_name="Retirement",
                        ),
                        AssetValuation(
                            product_type=ProductType.FUND,
                            asset_key="IE00BROKERAGE",
                            currency="EUR",
                            market_value=Dezimal(200),
                            quantity=Dezimal(1),
                            portfolio_name="Brokerage",
                        ),
                        AssetValuation(
                            product_type=ProductType.STOCK_ETF,
                            asset_key="ETF",
                            currency="EUR",
                            market_value=Dezimal(300),
                            quantity=Dezimal(1),
                            equity_type=EquityType.ETF,
                        ),
                        AssetValuation(
                            product_type=ProductType.STOCK_ETF,
                            asset_key="STOCK",
                            currency="EUR",
                            market_value=Dezimal(400),
                            quantity=Dezimal(1),
                            equity_type=EquityType.STOCK,
                        ),
                    ],
                )
            ],
            flows=[
                GainsFlow(
                    holder="broker",
                    product_type=ProductType.FUND,
                    asset_key="IE00RETIREMENT",
                    moment=moment,
                    amount=Dezimal(100),
                    currency="EUR",
                    quantity=Dezimal(1),
                    portfolio_name="Retirement",
                    transaction_type=TxType.BUY,
                ),
                GainsFlow(
                    holder="broker",
                    product_type=ProductType.FUND,
                    asset_key="IE00BROKERAGE",
                    moment=moment,
                    amount=Dezimal(200),
                    currency="EUR",
                    quantity=Dezimal(1),
                    portfolio_name="Brokerage",
                    transaction_type=TxType.BUY,
                ),
                GainsFlow(
                    holder="broker",
                    product_type=ProductType.STOCK_ETF,
                    asset_key="ETF",
                    moment=moment,
                    amount=Dezimal(300),
                    currency="EUR",
                    quantity=Dezimal(1),
                    equity_type=EquityType.ETF,
                    transaction_type=TxType.BUY,
                ),
                GainsFlow(
                    holder="broker",
                    product_type=ProductType.STOCK_ETF,
                    asset_key="STOCK",
                    moment=moment,
                    amount=Dezimal(400),
                    currency="EUR",
                    quantity=Dezimal(1),
                    equity_type=EquityType.STOCK,
                    transaction_type=TxType.BUY,
                ),
            ],
        )

        result = await use_case.execute(
            GainsTimelineQuery(
                assets=[
                    GainsAssetFilter(
                        product_type=ProductType.FUND,
                        portfolio_names=["Retirement"],
                    ),
                    GainsAssetFilter(
                        product_type=ProductType.STOCK_ETF,
                        equity_types=[EquityType.ETF],
                    ),
                ],
                entities=[uuid4()],
            )
        )

        metrics = result.points[0].metrics
        assert metrics.value == Dezimal(400)
        assert metrics.net_contributions == Dezimal(400)
        assert metrics.gain == Dezimal(0)

    @pytest.mark.asyncio
    async def test_filters_crypto_values_and_flows_by_wallet(self):
        wallet_id = uuid4()
        other_wallet_id = uuid4()
        moment = datetime(2025, 1, 1, 12)
        use_case, _ = _build(
            [
                AssetSnapshot(
                    holder="wallets",
                    moment=moment,
                    valuations=[
                        AssetValuation(
                            product_type=ProductType.CRYPTO,
                            asset_key="BTC",
                            currency="EUR",
                            market_value=Dezimal(100),
                            quantity=Dezimal(1),
                            wallet_id=wallet_id,
                        ),
                        AssetValuation(
                            product_type=ProductType.CRYPTO,
                            asset_key="ETH",
                            currency="EUR",
                            market_value=Dezimal(200),
                            quantity=Dezimal(2),
                            wallet_id=other_wallet_id,
                        ),
                    ],
                )
            ],
            flows=[
                GainsFlow(
                    holder="wallets",
                    product_type=ProductType.CRYPTO,
                    asset_key="BTC",
                    moment=moment,
                    amount=Dezimal(100),
                    currency="EUR",
                    quantity=Dezimal(1),
                    transaction_type=TxType.BUY,
                    wallet_id=wallet_id,
                ),
                GainsFlow(
                    holder="wallets",
                    product_type=ProductType.CRYPTO,
                    asset_key="BTC",
                    moment=moment,
                    amount=Dezimal(50),
                    currency="EUR",
                    quantity=Dezimal("0.5"),
                    transaction_type=TxType.BUY,
                ),
            ],
        )

        result = await use_case.execute(
            GainsTimelineQuery(
                assets=[
                    GainsAssetFilter(
                        product_type=ProductType.CRYPTO,
                        wallet_ids=[wallet_id],
                    )
                ],
                entities=[uuid4()],
            )
        )

        metrics = result.points[0].metrics
        assert metrics.value == Dezimal(100)
        assert metrics.net_contributions == Dezimal(100)
        assert metrics.gain == Dezimal(0)

    @pytest.mark.asyncio
    async def test_sums_values_per_holder_in_networth_order(self):
        first_holder_values = (
            "1534.3740",
            "475.7239",
            "927.2671",
            "2243.7967",
            "683.2371",
            "7617.2161",
            "1901.6370",
        )
        second_holder_values = (
            ("GBP", "5500.0"),
            ("USD", "110.0"),
            ("EUR", "900.0"),
            ("EUR", "500.0"),
        )
        first_holder = [
            AssetValuation(
                product_type=ProductType.FUND,
                asset_key=f"first-{index}",
                currency="EUR",
                market_value=Dezimal(value),
            )
            for index, value in enumerate(first_holder_values)
        ]
        second_holder = [
            AssetValuation(
                product_type=ProductType.FUND,
                asset_key=f"second-{index}",
                currency=currency,
                market_value=Dezimal(value),
            )
            for index, (currency, value) in enumerate(second_holder_values)
        ]
        rates = {
            "EUR": {
                "GBP": Dezimal("0.85650695"),
                "USD": Dezimal("1.15232445"),
            }
        }
        use_case, _ = _build(
            [
                AssetSnapshot(
                    holder="first",
                    moment=datetime(2025, 1, 1, 12),
                    valuations=first_holder,
                ),
                AssetSnapshot(
                    holder="second",
                    moment=datetime(2025, 1, 1, 12),
                    valuations=second_holder,
                ),
            ],
            rates=rates,
        )
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.FUND)],
            entities=[uuid4()],
        )

        result = await use_case.execute(query)

        first_total = sum(
            (valuation.market_value for valuation in first_holder), Dezimal(0)
        )
        second_total = sum(
            (
                valuation.market_value
                if valuation.currency == "EUR"
                else valuation.market_value / rates["EUR"][valuation.currency]
                for valuation in second_holder
            ),
            Dezimal(0),
        )
        flat_total = sum(
            (
                valuation.market_value
                if valuation.currency == "EUR"
                else valuation.market_value / rates["EUR"][valuation.currency]
                for valuation in [*first_holder, *second_holder]
            ),
            Dezimal(0),
        )

        assert first_total + second_total != flat_total
        assert result.points[0].metrics.value == first_total + second_total

    @pytest.mark.asyncio
    async def test_revalues_historic_commodity_values_without_transactions(self):
        first_day = date(2025, 1, 1)
        second_day = date(2025, 1, 2)
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = HistoricMetalRates(
            unit=WeightUnit.TROY_OUNCE,
            days=(first_day, second_day),
            prices={"EUR": (Dezimal(100), Dezimal(110))},
        )
        use_case, _ = _build(
            [
                AssetSnapshot(
                    holder="commodity-holder",
                    moment=datetime(2025, 1, 1, 12),
                    valuations=[
                        AssetValuation(
                            product_type=ProductType.COMMODITY,
                            asset_key="GOLD:Gold Coins",
                            currency="EUR",
                            market_value=Dezimal(100),
                            quantity=Dezimal(1),
                            cost_basis=Dezimal(100),
                            commodity_type=CommodityType.GOLD,
                            weight=Dezimal(1),
                            weight_unit=WeightUnit.TROY_OUNCE,
                        )
                    ],
                )
            ],
            metal=metal,
        )
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.COMMODITY)],
            entities=[uuid4()],
        )

        result = await use_case.execute(query)

        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[first_day].value == Dezimal(100)
        assert by_day[second_day].value == Dezimal(110)
        assert by_day[second_day].net_contributions == Dezimal(100)
        assert by_day[second_day].gain == Dezimal(10)
        metal.get_partial_historic_rates.assert_awaited_once_with(CommodityType.GOLD)

    @pytest.mark.asyncio
    async def test_skips_historic_metal_request_without_affected_commodity(self):
        metal = AsyncMock()
        use_case, _ = _build(
            [
                AssetSnapshot(
                    holder="commodity-holder",
                    moment=datetime.combine(
                        COMMODITY_HISTORIC_CUTOFF, datetime.min.time()
                    ),
                    valuations=[
                        AssetValuation(
                            product_type=ProductType.COMMODITY,
                            asset_key="GOLD:Gold Coins",
                            currency="EUR",
                            market_value=Dezimal(100),
                            quantity=Dezimal(1),
                            cost_basis=Dezimal(100),
                            commodity_type=CommodityType.GOLD,
                            weight=Dezimal(1),
                            weight_unit=WeightUnit.TROY_OUNCE,
                        )
                    ],
                )
            ],
            metal=metal,
        )
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.COMMODITY)],
            entities=[uuid4()],
        )

        await use_case.execute(query)

        metal.get_partial_historic_rates.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_infers_crypto_contribution_from_quantity_without_transactions(self):
        first_day = date(2025, 1, 1)
        second_day = date(2025, 1, 2)
        use_case, _ = _build(
            [
                _snapshot(first_day, "1", "100"),
                _snapshot(second_day, "2", "250"),
            ]
        )

        result = await use_case.execute(_query())

        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[first_day].net_contributions == Dezimal(100)
        assert by_day[second_day].net_contributions == Dezimal(225)
        assert by_day[second_day].gain == Dezimal(25)
        assert by_day[second_day].period_return == Dezimal(
            "0.111111111111111111111111111"
        )
        assert by_day[second_day].index == Dezimal("111.1111111111111111111111111")

    @pytest.mark.asyncio
    async def test_uses_crypto_buy_transaction_without_double_counting_quantity(self):
        first_day = date(2025, 1, 1)
        second_day = date(2025, 1, 2)
        use_case, _ = _build(
            [
                _snapshot(first_day, "1", "100"),
                _snapshot(second_day, "2", "250"),
            ],
            [_flow(second_day, TxType.BUY, "125", quantity="1")],
        )

        result = await use_case.execute(_query())

        metrics = result.points[-1].metrics
        assert metrics.net_contributions == Dezimal(225)
        assert metrics.gain == Dezimal(25)
        assert metrics.period_return == Dezimal("0.111111111111111111111111111")
        assert metrics.index == Dezimal("111.1111111111111111111111111")

    @pytest.mark.asyncio
    async def test_treats_dividend_as_withdrawal_for_time_weighted_return(self):
        first_day = date(2025, 1, 1)
        second_day = date(2025, 1, 2)
        use_case, _ = _build(
            [
                _snapshot(first_day, "1", "100"),
                _snapshot(second_day, "1", "95"),
            ],
            [_flow(second_day, TxType.DIVIDEND, "5")],
        )

        result = await use_case.execute(_query())

        metrics = result.points[-1].metrics
        assert metrics.net_contributions == Dezimal(95)
        assert metrics.gain == Dezimal(0)
        assert metrics.period_return == Dezimal(0)
        assert metrics.index == Dezimal(100)

    @pytest.mark.asyncio
    async def test_dividend_credits_gain_net_of_withholding_tax(self):
        first_day = date(2025, 1, 1)
        second_day = date(2025, 1, 2)
        dividend = GainsFlow(
            holder="wallet",
            product_type=ProductType.CRYPTO,
            asset_key="BTC",
            moment=datetime(second_day.year, second_day.month, second_day.day, 12),
            amount=Dezimal(5),
            currency="EUR",
            retentions=Dezimal(1),
            transaction_type=TxType.DIVIDEND,
        )
        use_case, _ = _build(
            [
                _snapshot(first_day, "1", "100"),
                _snapshot(second_day, "1", "100"),
            ],
            [dividend],
        )

        result = await use_case.execute(_query())

        metrics = result.points[-1].metrics
        assert metrics.net_contributions == Dezimal(96)
        assert metrics.gain == Dezimal(4)

    @pytest.mark.asyncio
    async def test_accrues_deposit_interest_between_position_snapshots(self):
        first_day = date(2025, 1, 1)
        second_day = date(2025, 1, 2)
        snapshot = AssetSnapshot(
            holder="deposit-holder",
            moment=datetime(first_day.year, first_day.month, first_day.day, 12),
            valuations=[
                AssetValuation(
                    product_type=ProductType.DEPOSIT,
                    asset_key="deposit",
                    currency="EUR",
                    market_value=Dezimal(100),
                    cost_basis=Dezimal(100),
                    interest_rate=Dezimal("0.365"),
                    start_date=first_day,
                    maturity=date(2025, 1, 10),
                )
            ],
        )
        use_case, _ = _build([snapshot])
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.DEPOSIT)],
            entities=[uuid4()],
            to_date=second_day,
            accrue_fixed_income=FixedIncomeAccrual.GROSS,
        )

        result = await use_case.execute(query)

        metrics = result.points[-1].metrics
        assert metrics.value == Dezimal("100.1")
        assert metrics.gain == Dezimal("0.1")
        assert metrics.period_return == Dezimal("0.001")
        assert metrics.index == Dezimal("100.1")

    @pytest.mark.asyncio
    async def test_defaults_to_no_fixed_income_accrual(self):
        first_day = date(2025, 1, 1)
        second_day = date(2025, 1, 2)
        snapshot = AssetSnapshot(
            holder="deposit-holder",
            moment=datetime(first_day.year, first_day.month, first_day.day, 12),
            valuations=[
                AssetValuation(
                    product_type=ProductType.DEPOSIT,
                    asset_key="deposit",
                    currency="EUR",
                    market_value=Dezimal(100),
                    cost_basis=Dezimal(100),
                    interest_rate=Dezimal("0.365"),
                    start_date=first_day,
                    maturity=date(2025, 1, 10),
                )
            ],
        )
        use_case, _ = _build([snapshot])
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.DEPOSIT)],
            entities=[uuid4()],
            to_date=second_day,
        )

        result = await use_case.execute(query)

        assert [point.date for point in result.points] == [first_day]
        assert result.points[0].metrics.value == Dezimal(100)
        assert result.points[0].metrics.gain == Dezimal(0)

    @pytest.mark.asyncio
    async def test_accrues_matured_deposit_from_known_net_interest(self):
        first_day = date(2025, 1, 1)
        before_maturity = date(2025, 1, 4)
        maturity_day = date(2025, 1, 5)
        valuation = AssetValuation(
            product_type=ProductType.DEPOSIT,
            asset_key="deposit",
            currency="EUR",
            market_value=Dezimal(100),
            cost_basis=Dezimal(100),
            interest_rate=Dezimal("0.365"),
            start_date=first_day,
            maturity=maturity_day,
        )

        def snapshot(day, valuations):
            return AssetSnapshot(
                holder="deposit-holder",
                moment=datetime(day.year, day.month, day.day, 12),
                valuations=valuations,
            )

        def flow(day, transaction_type, amount, retentions="0", net_amount=None):
            return GainsFlow(
                holder="deposit-holder",
                product_type=ProductType.DEPOSIT,
                asset_key="deposit",
                moment=datetime(day.year, day.month, day.day, 12),
                amount=Dezimal(amount),
                currency="EUR",
                retentions=Dezimal(retentions),
                net_amount=Dezimal(net_amount) if net_amount is not None else None,
                transaction_type=transaction_type,
            )

        use_case, _ = _build(
            [
                snapshot(first_day, [valuation]),
                snapshot(before_maturity, [valuation]),
                snapshot(maturity_day, []),
            ],
            [
                flow(first_day, TxType.INVESTMENT, "100"),
                flow(maturity_day, TxType.REPAYMENT, "100"),
                flow(maturity_day, TxType.INTEREST, "0.4", "0.08", "0.32"),
            ],
        )
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.DEPOSIT)],
            entities=[uuid4()],
            to_date=maturity_day,
            accrue_fixed_income=FixedIncomeAccrual.NET,
        )

        result = await use_case.execute(query)

        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[before_maturity].gain == Dezimal("0.24")
        assert by_day[maturity_day].gain == Dezimal("0.32")

    @pytest.mark.asyncio
    async def test_does_not_double_count_opening_cost_basis_and_buy_transaction(self):
        first_day = date(2025, 1, 1)
        use_case, _ = _build(
            [_snapshot(first_day, "1", "100", cost_basis="100")],
            [_flow(first_day, TxType.BUY, "100", quantity="1")],
        )

        result = await use_case.execute(_query())

        assert result.points[0].metrics.net_contributions == Dezimal(100)
        assert result.points[0].metrics.gain == Dezimal(0)

    @pytest.mark.asyncio
    async def test_reconciles_buy_before_first_position_snapshot(self):
        first_snapshot_day = date(2025, 1, 1)
        buy_day = date(2025, 1, 2)
        valuation_day = date(2025, 1, 3)

        def empty_snapshot(snapshot_day):
            return AssetSnapshot(
                holder="wallet",
                moment=datetime(
                    snapshot_day.year, snapshot_day.month, snapshot_day.day, 12
                ),
            )

        use_case, _ = _build(
            [
                empty_snapshot(first_snapshot_day),
                empty_snapshot(buy_day),
                _snapshot(valuation_day, "1", "95", cost_basis="100"),
            ],
            [
                _flow(date(2024, 11, 1), TxType.BUY, "100", quantity="1"),
                _flow(date(2024, 11, 2), TxType.SELL, "120", quantity="1"),
                _flow(buy_day, TxType.BUY, "100", quantity="1"),
            ],
        )

        result = await use_case.execute(_query())

        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[date(2024, 11, 1)].value == Dezimal(100)
        assert by_day[date(2024, 11, 1)].gain == Dezimal(0)
        assert by_day[date(2024, 11, 2)].value == Dezimal(0)
        assert by_day[date(2024, 11, 2)].gain == Dezimal(20)
        assert by_day[date(2024, 12, 15)].value == Dezimal(0)
        assert by_day[date(2024, 12, 15)].gain == Dezimal(20)
        assert by_day[buy_day].value == Dezimal(100)
        assert by_day[buy_day].gain == Dezimal(20)
        metrics = result.points[-1].metrics
        assert metrics.value == Dezimal(95)
        assert metrics.cost_basis == Dezimal(100)
        assert metrics.net_contributions == Dezimal(80)
        assert metrics.gain == Dezimal(15)
        assert result.quality == GainsQuality.ESTIMATED

    @pytest.mark.asyncio
    async def test_waits_for_asset_snapshot_before_emitting_unobserved_buy(self):
        first_day = date(2025, 1, 1)
        buy_day = date(2025, 1, 2)
        observed_day = date(2025, 1, 3)
        unrelated_snapshot = AssetSnapshot(
            holder="other-wallet",
            moment=datetime(buy_day.year, buy_day.month, buy_day.day, 12),
        )
        use_case, _ = _build(
            [
                _snapshot(first_day, "1", "100", cost_basis="100"),
                unrelated_snapshot,
                _snapshot(observed_day, "2", "210", cost_basis="200"),
            ],
            [_flow(buy_day, TxType.BUY, "100", quantity="1")],
        )

        result = await use_case.execute(_query())

        assert [point.date for point in result.points] == [first_day, observed_day]
        metrics = result.points[-1].metrics
        assert metrics.value == Dezimal(210)
        assert metrics.net_contributions == Dezimal(200)
        assert metrics.gain == Dezimal(10)

    @pytest.mark.asyncio
    async def test_emits_observed_holder_while_another_market_flow_is_pending(self):
        first_day = date(2025, 1, 1)
        stale_day = date(2025, 1, 2)

        def valuation(asset_key, market_value):
            return AssetValuation(
                product_type=ProductType.CRYPTO,
                asset_key=asset_key,
                currency="EUR",
                quantity=Dezimal(1),
                market_value=Dezimal(market_value),
                cost_basis=Dezimal(100),
            )

        def snapshot(day, holder, asset_key, market_value):
            return AssetSnapshot(
                holder=holder,
                moment=datetime(day.year, day.month, day.day, 12),
                valuations=[valuation(asset_key, market_value)],
            )

        use_case, _ = _build(
            [
                snapshot(first_day, "pending", "PENDING", "100"),
                snapshot(first_day, "observed", "OBSERVED", "100"),
                snapshot(stale_day, "pending", "PENDING", "95"),
                snapshot(stale_day, "observed", "OBSERVED", "110"),
            ],
            [
                GainsFlow(
                    holder="pending",
                    product_type=ProductType.CRYPTO,
                    asset_key="PENDING",
                    moment=datetime(stale_day.year, stale_day.month, stale_day.day, 12),
                    amount=Dezimal(100),
                    currency="EUR",
                    quantity=Dezimal(1),
                    transaction_type=TxType.BUY,
                )
            ],
        )

        result = await use_case.execute(_query())

        assert [point.date for point in result.points] == [first_day, stale_day]
        metrics = result.points[-1].metrics
        assert metrics.value == Dezimal(205)
        assert metrics.net_contributions == Dezimal(200)
        assert metrics.gain == Dezimal(5)

    @pytest.mark.asyncio
    async def test_releases_historical_quantity_mismatch_before_later_buy(self):
        first_day = date(2025, 1, 1)
        mismatched_observation_day = date(2025, 1, 3)
        later_buy_day = date(2025, 1, 4)
        later_observation_day = date(2025, 1, 5)
        use_case, _ = _build(
            [
                _snapshot(first_day, "10", "100", cost_basis="100"),
                _snapshot(mismatched_observation_day, "12", "120", cost_basis="120"),
                _snapshot(later_observation_day, "13", "130", cost_basis="130"),
            ],
            [
                _flow(date(2025, 1, 2), TxType.BUY, "10", quantity="1"),
                _flow(later_buy_day, TxType.BUY, "10", quantity="1"),
            ],
        )

        result = await use_case.execute(_query())

        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[first_day].value == Dezimal(100)
        assert by_day[mismatched_observation_day].value == Dezimal(120)
        metrics = by_day[later_observation_day]
        assert metrics.value == Dezimal(130)
        assert metrics.net_contributions == Dezimal(130)
        assert metrics.gain == Dezimal(0)
        assert all(
            by_day[day].period_return == Dezimal(0)
            for day in (date(2025, 1, 2), date(2025, 1, 4))
        )

    @pytest.mark.asyncio
    async def test_waits_for_quantity_change_after_stale_asset_snapshot(self):
        first_day = date(2025, 1, 1)
        buy_day = date(2025, 1, 2)
        observed_day = date(2025, 1, 3)
        use_case, _ = _build(
            [
                _snapshot(first_day, "1", "100", cost_basis="100"),
                _snapshot(buy_day, "1", "95", cost_basis="100"),
                _snapshot(observed_day, "2", "210", cost_basis="200"),
            ],
            [_flow(buy_day, TxType.BUY, "100", quantity="1")],
        )

        result = await use_case.execute(_query())

        assert [point.date for point in result.points] == [first_day, observed_day]
        metrics = result.points[-1].metrics
        assert metrics.value == Dezimal(210)
        assert metrics.net_contributions == Dezimal(200)
        assert metrics.gain == Dezimal(10)

    @pytest.mark.asyncio
    async def test_replaces_stale_fund_after_full_transfer_arrives(self):
        first_day = date(2025, 1, 1)
        transfer_day = date(2025, 1, 2)
        completion_day = date(2025, 1, 3)

        def valuation(asset_key, quantity, value, cost_basis):
            return AssetValuation(
                product_type=ProductType.FUND,
                asset_key=asset_key,
                currency="EUR",
                quantity=Dezimal(quantity),
                market_value=Dezimal(value),
                cost_basis=Dezimal(cost_basis),
            )

        def snapshot(day, valuations):
            return AssetSnapshot(
                holder="wallet",
                moment=datetime(day.year, day.month, day.day, 12),
                valuations=valuations,
            )

        def flow(day, asset_key, transaction_type, amount, quantity):
            return GainsFlow(
                holder="wallet",
                product_type=ProductType.FUND,
                asset_key=asset_key,
                moment=datetime(day.year, day.month, day.day, 12),
                amount=Dezimal(amount),
                currency="EUR",
                quantity=Dezimal(quantity),
                transaction_type=transaction_type,
            )

        use_case, _ = _build(
            [
                snapshot(first_day, [valuation("OLD", "100", "1000", "900")]),
                snapshot(
                    transfer_day,
                    [
                        valuation("OLD", "100", "1000", "900"),
                        valuation("NEW", "2", "20", "20"),
                    ],
                ),
                snapshot(
                    completion_day,
                    [
                        valuation("OLD", "100", "1000", "900"),
                        valuation("NEW", "102", "1000", "1020"),
                    ],
                ),
            ],
            [
                flow(transfer_day, "OLD", TxType.TRANSFER_OUT, "1000", "100"),
                flow(transfer_day, "NEW", TxType.TRANSFER_IN, "1000", "100"),
            ],
        )
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.FUND)],
            entities=[uuid4()],
        )

        result = await use_case.execute(query)

        metrics = result.points[-1].metrics
        assert metrics.value == Dezimal(1000)
        assert metrics.cost_basis == Dezimal(1020)
        assert metrics.index == Dezimal(100)

    @pytest.mark.asyncio
    async def test_retains_fixed_income_rate_when_later_snapshot_reports_zero(self):
        first_day = date(2025, 1, 1)
        second_day = date(2025, 1, 2)

        def valuation(rate):
            return AssetValuation(
                product_type=ProductType.REAL_ESTATE_CF,
                asset_key="Project",
                currency="EUR",
                market_value=Dezimal(100),
                cost_basis=Dezimal(100),
                interest_rate=Dezimal(rate),
                start_date=first_day,
                maturity=date(2025, 1, 10),
            )

        def snapshot(day, value):
            return AssetSnapshot(
                holder="holder",
                moment=datetime(day.year, day.month, day.day, 12),
                valuations=[value],
            )

        use_case, _ = _build(
            [
                snapshot(first_day, valuation("0.365")),
                snapshot(second_day, valuation(0)),
            ]
        )
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.REAL_ESTATE_CF)],
            entities=[uuid4()],
            to_date=second_day,
            accrue_fixed_income=FixedIncomeAccrual.GROSS,
        )

        result = await use_case.execute(query)

        assert result.points[-1].metrics.value == Dezimal("100.1")

    @pytest.mark.asyncio
    async def test_accrues_real_estate_cf_net_interest_through_partial_repayment(self):
        first_day = date(2025, 1, 1)
        before_payment = date(2025, 1, 2)
        payment_day = date(2025, 1, 3)

        def valuation(amount):
            return AssetValuation(
                product_type=ProductType.REAL_ESTATE_CF,
                asset_key="Project",
                currency="EUR",
                market_value=Dezimal(amount),
                cost_basis=Dezimal(amount),
                interest_rate=Dezimal("0.365"),
                start_date=first_day,
                maturity=date(2025, 1, 10),
            )

        def snapshot(day, value):
            return AssetSnapshot(
                holder="holder",
                moment=datetime(day.year, day.month, day.day, 12),
                valuations=[value],
            )

        def flow(transaction_type, amount, retentions="0", net_amount=None):
            return GainsFlow(
                holder="holder",
                product_type=ProductType.REAL_ESTATE_CF,
                asset_key="Project",
                moment=datetime(
                    payment_day.year, payment_day.month, payment_day.day, 12
                )
                if transaction_type != TxType.INVESTMENT
                else datetime(first_day.year, first_day.month, first_day.day, 12),
                amount=Dezimal(amount),
                currency="EUR",
                retentions=Dezimal(retentions),
                net_amount=Dezimal(net_amount) if net_amount is not None else None,
                transaction_type=transaction_type,
            )

        use_case, _ = _build(
            [
                snapshot(first_day, valuation("500")),
                snapshot(before_payment, valuation("500")),
                snapshot(payment_day, valuation("400")),
            ],
            [
                flow(TxType.INVESTMENT, "500"),
                flow(TxType.REPAYMENT, "100"),
                flow(TxType.INTEREST, "10", "2", "8"),
            ],
        )
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.REAL_ESTATE_CF)],
            entities=[uuid4()],
            to_date=payment_day,
            accrue_fixed_income=FixedIncomeAccrual.NET,
        )

        result = await use_case.execute(query)

        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[before_payment].gain == Dezimal(4)
        assert by_day[payment_day].gain == Dezimal(8)

    @pytest.mark.asyncio
    async def test_holds_interest_until_delayed_partial_repayment_snapshot(self):
        first_day = date(2025, 1, 1)
        before_payment = date(2025, 1, 2)
        payment_day = date(2025, 1, 3)
        snapshot_day = date(2025, 1, 4)

        def valuation(amount):
            return AssetValuation(
                product_type=ProductType.REAL_ESTATE_CF,
                asset_key="Project",
                currency="EUR",
                market_value=Dezimal(amount),
                cost_basis=Dezimal(amount),
                interest_rate=Dezimal("0.365"),
                start_date=first_day,
                maturity=date(2025, 1, 10),
            )

        def snapshot(day, value):
            return AssetSnapshot(
                holder="holder",
                moment=datetime(day.year, day.month, day.day, 12),
                valuations=[value],
            )

        def flow(transaction_type, amount, retentions="0", net_amount=None):
            return GainsFlow(
                holder="holder",
                product_type=ProductType.REAL_ESTATE_CF,
                asset_key="Project",
                moment=datetime(
                    payment_day.year, payment_day.month, payment_day.day, 12
                )
                if transaction_type != TxType.INVESTMENT
                else datetime(first_day.year, first_day.month, first_day.day, 12),
                amount=Dezimal(amount),
                currency="EUR",
                retentions=Dezimal(retentions),
                net_amount=Dezimal(net_amount) if net_amount is not None else None,
                transaction_type=transaction_type,
            )

        use_case, _ = _build(
            [
                snapshot(first_day, valuation("500")),
                snapshot(before_payment, valuation("500")),
                snapshot(payment_day, valuation("500")),
                snapshot(snapshot_day, valuation("400")),
            ],
            [
                flow(TxType.INVESTMENT, "500"),
                flow(TxType.REPAYMENT, "100"),
                flow(TxType.INTEREST, "10", "2", "8"),
            ],
        )
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.REAL_ESTATE_CF)],
            entities=[uuid4()],
            to_date=snapshot_day,
            accrue_fixed_income=FixedIncomeAccrual.NET,
        )

        result = await use_case.execute(query)

        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[payment_day].gain == Dezimal(8)
        assert by_day[snapshot_day].gain == Dezimal("8.4")

    @pytest.mark.asyncio
    async def test_accounts_for_completed_fixed_income_without_snapshot(self):
        first_day = date(2025, 1, 1)
        snapshot_day = date(2025, 1, 2)
        active = AssetValuation(
            product_type=ProductType.FACTORING,
            asset_key="active",
            currency="EUR",
            market_value=Dezimal(100),
            cost_basis=Dezimal(100),
            interest_rate=Dezimal(0),
            start_date=first_day,
            maturity=date(2025, 1, 10),
        )
        snapshot = AssetSnapshot(
            holder="holder",
            moment=datetime(
                snapshot_day.year, snapshot_day.month, snapshot_day.day, 12
            ),
            valuations=[active],
        )

        def flow(transaction_type, amount):
            return GainsFlow(
                holder="holder",
                product_type=ProductType.FACTORING,
                asset_key="completed",
                moment=datetime(first_day.year, first_day.month, first_day.day, 12),
                amount=Dezimal(amount),
                currency="EUR",
                transaction_type=transaction_type,
            )

        use_case, _ = _build(
            [snapshot],
            [
                flow(TxType.INVESTMENT, "100"),
                flow(TxType.REPAYMENT, "100"),
                flow(TxType.INTEREST, "10"),
            ],
        )
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.FACTORING)],
            entities=[uuid4()],
            to_date=snapshot_day,
            accrue_fixed_income=FixedIncomeAccrual.NONE,
        )

        result = await use_case.execute(query)

        metrics = result.points[-1].metrics
        assert metrics.net_contributions == Dezimal(90)
        assert metrics.gain == Dezimal(10)

    @pytest.mark.asyncio
    async def test_skips_zero_point_between_deposit_maturity_and_rollover(self):
        first_day = date(2025, 1, 1)
        maturity_day = date(2025, 1, 2)
        rollover_day = date(2025, 1, 3)

        def valuation(asset_key, amount):
            return AssetValuation(
                product_type=ProductType.DEPOSIT,
                asset_key=asset_key,
                currency="EUR",
                market_value=Dezimal(amount),
                cost_basis=Dezimal(amount),
                interest_rate=Dezimal(0),
                start_date=first_day,
                maturity=maturity_day,
            )

        def snapshot(day, valuations):
            return AssetSnapshot(
                holder="holder",
                moment=datetime(day.year, day.month, day.day, 12),
                valuations=valuations,
            )

        def flow(day, asset_key, transaction_type, amount):
            return GainsFlow(
                holder="holder",
                product_type=ProductType.DEPOSIT,
                asset_key=asset_key,
                moment=datetime(day.year, day.month, day.day, 12),
                amount=Dezimal(amount),
                currency="EUR",
                transaction_type=transaction_type,
            )

        use_case, _ = _build(
            [
                snapshot(first_day, [valuation("old", "1000")]),
                snapshot(maturity_day, []),
                snapshot(rollover_day, [valuation("new", "1000")]),
            ],
            [
                flow(maturity_day, "old", TxType.REPAYMENT, "1000"),
                flow(maturity_day, "old", TxType.INTEREST, "10"),
                flow(maturity_day, "new", TxType.INVESTMENT, "1000"),
            ],
        )
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.DEPOSIT)],
            entities=[uuid4()],
            accrue_fixed_income=FixedIncomeAccrual.NONE,
        )

        result = await use_case.execute(query)

        assert [point.date for point in result.points] == [first_day, rollover_day]
        assert result.points[-1].metrics.gain == Dezimal(10)

    @pytest.mark.asyncio
    async def test_stale_unreconciled_inflow_does_not_suppress_idle_days(self):
        stale_day = date(2024, 6, 1)
        first_day = date(2025, 1, 1)
        maturity_day = date(2025, 1, 2)
        reinvest_day = date(2025, 1, 6)

        def valuation(asset_key, amount):
            return AssetValuation(
                product_type=ProductType.FACTORING,
                asset_key=asset_key,
                currency="EUR",
                market_value=Dezimal(amount),
                cost_basis=Dezimal(amount),
                interest_rate=Dezimal(0),
                start_date=first_day,
                maturity=maturity_day,
            )

        def snapshot(day, valuations):
            return AssetSnapshot(
                holder="holder",
                moment=datetime(day.year, day.month, day.day, 12),
                valuations=valuations,
            )

        def flow(day, asset_key, transaction_type, amount):
            return GainsFlow(
                holder="holder",
                product_type=ProductType.FACTORING,
                asset_key=asset_key,
                moment=datetime(day.year, day.month, day.day, 12),
                amount=Dezimal(amount),
                currency="EUR",
                transaction_type=transaction_type,
            )

        use_case, _ = _build(
            [
                snapshot(first_day, [valuation("old", "1000")]),
                snapshot(maturity_day, []),
                snapshot(reinvest_day, [valuation("new", "1000")]),
            ],
            [
                # never reconciles against a snapshot - must not block the series
                flow(stale_day, "ghost", TxType.INVESTMENT, "500"),
                flow(maturity_day, "old", TxType.REPAYMENT, "1000"),
                flow(maturity_day, "old", TxType.INTEREST, "10"),
                flow(reinvest_day, "new", TxType.INVESTMENT, "1000"),
            ],
        )
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.FACTORING)],
            entities=[uuid4()],
            accrue_fixed_income=FixedIncomeAccrual.NONE,
        )

        result = await use_case.execute(query)

        emitted = {point.date for point in result.points}
        assert {date(2025, 1, 3), date(2025, 1, 4), date(2025, 1, 5)} <= emitted

    @pytest.mark.asyncio
    async def test_keeps_flat_points_while_no_deposit_is_held(self):
        first_day = date(2025, 1, 1)
        maturity_day = date(2025, 1, 2)
        reinvest_day = date(2025, 1, 6)

        def valuation(asset_key, amount):
            return AssetValuation(
                product_type=ProductType.DEPOSIT,
                asset_key=asset_key,
                currency="EUR",
                market_value=Dezimal(amount),
                cost_basis=Dezimal(amount),
                interest_rate=Dezimal(0),
                start_date=first_day,
                maturity=maturity_day,
            )

        def snapshot(day, valuations):
            return AssetSnapshot(
                holder="holder",
                moment=datetime(day.year, day.month, day.day, 12),
                valuations=valuations,
            )

        def flow(day, asset_key, transaction_type, amount):
            return GainsFlow(
                holder="holder",
                product_type=ProductType.DEPOSIT,
                asset_key=asset_key,
                moment=datetime(day.year, day.month, day.day, 12),
                amount=Dezimal(amount),
                currency="EUR",
                transaction_type=transaction_type,
            )

        use_case, _ = _build(
            [
                snapshot(first_day, [valuation("old", "1000")]),
                snapshot(maturity_day, []),
                snapshot(reinvest_day, [valuation("new", "1000")]),
            ],
            [
                flow(maturity_day, "old", TxType.REPAYMENT, "1000"),
                flow(maturity_day, "old", TxType.INTEREST, "10"),
                flow(reinvest_day, "new", TxType.INVESTMENT, "1000"),
            ],
        )
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.DEPOSIT)],
            entities=[uuid4()],
            accrue_fixed_income=FixedIncomeAccrual.NONE,
        )

        result = await use_case.execute(query)

        by_day = {point.date: point.metrics for point in result.points}
        assert [point.date for point in result.points] == [
            first_day,
            maturity_day,
            date(2025, 1, 3),
            date(2025, 1, 4),
            date(2025, 1, 5),
            reinvest_day,
        ]
        for idle_day in (date(2025, 1, 3), date(2025, 1, 4), date(2025, 1, 5)):
            assert by_day[idle_day].value == Dezimal(0)
            assert by_day[idle_day].gain == Dezimal(10)

    @pytest.mark.asyncio
    async def test_defers_deposit_rollover_flows_until_replacement_snapshot(self):
        first_day = date(2025, 1, 1)
        rollover_day = date(2025, 1, 2)
        replacement_day = date(2025, 1, 3)

        def valuation(asset_key, amount):
            return AssetValuation(
                product_type=ProductType.DEPOSIT,
                asset_key=asset_key,
                currency="EUR",
                market_value=Dezimal(amount),
                cost_basis=Dezimal(amount),
                interest_rate=Dezimal(0),
                start_date=first_day,
                maturity=rollover_day,
            )

        def snapshot(day, valuations):
            return AssetSnapshot(
                holder="holder",
                moment=datetime(day.year, day.month, day.day, 12),
                valuations=valuations,
            )

        def flow(asset_key, transaction_type, amount):
            return GainsFlow(
                holder="holder",
                product_type=ProductType.DEPOSIT,
                asset_key=asset_key,
                moment=datetime(
                    rollover_day.year, rollover_day.month, rollover_day.day, 12
                ),
                amount=Dezimal(amount),
                currency="EUR",
                transaction_type=transaction_type,
            )

        use_case, _ = _build(
            [
                snapshot(first_day, [valuation("old", "20000")]),
                snapshot(rollover_day, [valuation("old", "20000")]),
                snapshot(replacement_day, [valuation("new", "10000")]),
            ],
            [
                flow("old", TxType.REPAYMENT, "20000"),
                flow("old", TxType.INTEREST, "10"),
                flow("new", TxType.INVESTMENT, "10000"),
            ],
        )
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.DEPOSIT)],
            entities=[uuid4()],
            accrue_fixed_income=FixedIncomeAccrual.NONE,
        )

        result = await use_case.execute(query)

        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[rollover_day].gain == Dezimal(0)
        assert by_day[replacement_day].gain == Dezimal(10)
        assert by_day[replacement_day].period_return == Dezimal("0.0005")

    @pytest.mark.asyncio
    async def test_converts_fixed_income_accrual_to_target_currency(self):
        first_day = date(2025, 1, 1)
        second_day = date(2025, 1, 2)
        snapshot = AssetSnapshot(
            holder="deposit-holder",
            moment=datetime(first_day.year, first_day.month, first_day.day, 12),
            valuations=[
                AssetValuation(
                    product_type=ProductType.DEPOSIT,
                    asset_key="deposit",
                    currency="USD",
                    market_value=Dezimal(100),
                    cost_basis=Dezimal(100),
                    interest_rate=Dezimal("0.365"),
                    start_date=first_day,
                    maturity=date(2025, 1, 10),
                )
            ],
        )
        use_case, _ = _build([snapshot], rates={"EUR": {"USD": Dezimal(2)}})
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.DEPOSIT)],
            entities=[uuid4()],
            base_currency="EUR",
            to_date=second_day,
            accrue_fixed_income=FixedIncomeAccrual.GROSS,
        )

        result = await use_case.execute(query)

        metrics = result.points[-1].metrics
        assert metrics.value == Dezimal("50.05")
        assert metrics.gain == Dezimal("0.05")

    @pytest.mark.asyncio
    async def test_reuses_cache_until_data_version_changes(self):
        first_day = date(2025, 1, 1)
        use_case, port = _build([_snapshot(first_day, "1", "100")])
        query = _query()

        await use_case.execute(query)
        await use_case.execute(query)

        assert port.get_asset_snapshots.await_count == 1
        assert port.get_flows.await_count == 1
        assert port.get_settlements.await_count == 1

        port.get_data_version.return_value = "2"
        await use_case.execute(query)

        assert port.get_asset_snapshots.await_count == 2

    @pytest.mark.asyncio
    async def test_wallet_filters_have_distinct_cache_entries(self):
        first_day = date(2025, 1, 1)
        entity_id = uuid4()
        use_case, port = _build([_snapshot(first_day, "1", "100")])

        for wallet_id in (uuid4(), uuid4()):
            await use_case.execute(
                GainsTimelineQuery(
                    assets=[
                        GainsAssetFilter(
                            product_type=ProductType.CRYPTO,
                            wallet_ids=[wallet_id],
                        )
                    ],
                    entities=[entity_id],
                )
            )

        assert port.get_asset_snapshots.await_count == 2

    @pytest.mark.asyncio
    async def test_uses_actual_fixed_income_settlement_proceeds(self):
        first_day = date(2025, 1, 1)
        settlement_day = date(2025, 1, 2)
        snapshot = AssetSnapshot(
            holder="holder",
            moment=datetime(first_day.year, first_day.month, first_day.day, 12),
            valuations=[
                AssetValuation(
                    product_type=ProductType.FACTORING,
                    asset_key="Project",
                    currency="EUR",
                    market_value=Dezimal(100),
                    cost_basis=Dezimal(100),
                    interest_rate=Dezimal("0.365"),
                    start_date=first_day,
                    maturity=date(2025, 1, 10),
                )
            ],
        )
        settlement = GainsSettlement(
            holder="holder",
            product_type=ProductType.FACTORING,
            asset_key="Project",
            moment=datetime(
                settlement_day.year, settlement_day.month, settlement_day.day, 12
            ),
            net_proceeds=Dezimal(110),
            currency="EUR",
        )
        use_case, _ = _build([snapshot], settlements=[settlement])
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.FACTORING)],
            entities=[uuid4()],
            to_date=settlement_day,
        )

        result = await use_case.execute(query)

        metrics = result.points[-1].metrics
        assert metrics.value == Dezimal(0)
        assert metrics.net_contributions == Dezimal(-10)
        assert metrics.gain == Dezimal(10)
        assert metrics.period_return == Dezimal("0.1")


class TestGetGainsTimelineReplay:
    @pytest.mark.asyncio
    async def test_transactions_only_entity_shows_history_and_realized_gain(self):
        buy_day = date(2024, 11, 1)
        sell_day = date(2024, 11, 2)
        use_case, _ = _build(
            [],
            [
                _flow(buy_day, TxType.BUY, "100", quantity="1"),
                _flow(sell_day, TxType.SELL, "120", quantity="1"),
            ],
        )

        result = await use_case.execute(_query())

        assert result.points[0].date == buy_day
        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[buy_day].value == Dezimal(100)
        assert by_day[buy_day].net_contributions == Dezimal(100)
        assert by_day[buy_day].gain == Dezimal(0)
        assert by_day[sell_day].value == Dezimal(0)
        assert by_day[sell_day].net_contributions == Dezimal(-20)
        assert by_day[sell_day].gain == Dezimal(20)
        assert by_day[sell_day].period_return == Dezimal("0.2")
        assert by_day[sell_day + timedelta(days=1)].value == Dezimal(0)
        assert by_day[sell_day + timedelta(days=1)].gain == Dezimal(20)
        assert result.quality == GainsQuality.ESTIMATED
        assert result.warnings == [
            "Some positions were reconstructed from transactions without "
            "stored market values; valuations before the first stored "
            "position use transaction cost."
        ]

    @pytest.mark.asyncio
    async def test_replay_xirr_converges_over_long_period(self):
        buy_day = date(2024, 1, 1)
        sell_day = date(2025, 1, 1)
        use_case, _ = _build(
            [],
            [
                _flow(buy_day, TxType.BUY, "100", quantity="1"),
                _flow(sell_day, TxType.SELL, "110", quantity="1"),
            ],
        )

        result = await use_case.execute(_query())

        assert result.xirr is not None
        assert Dezimal("0.09") < result.xirr < Dezimal("0.11")
        assert result.annualized_xirr is not None

    @pytest.mark.asyncio
    async def test_open_replayed_position_extends_to_yesterday(self):
        buy_day = date(2024, 11, 1)
        use_case, _ = _build(
            [],
            [_flow(buy_day, TxType.BUY, "100", quantity="2")],
        )

        result = await use_case.execute(_query())

        yesterday = date.today() - timedelta(days=1)
        assert result.points[0].date == buy_day
        assert result.points[-1].date == yesterday
        metrics = result.points[-1].metrics
        assert metrics.value == Dezimal(100)
        assert metrics.net_contributions == Dezimal(100)
        assert metrics.gain == Dezimal(0)
        assert all(point.metrics.period_return == Dezimal(0) for point in result.points)

    @pytest.mark.asyncio
    async def test_partial_sell_keeps_proportional_book_value(self):
        buy_day = date(2024, 11, 1)
        sell_day = date(2024, 11, 2)
        use_case, _ = _build(
            [],
            [
                _flow(buy_day, TxType.BUY, "200", quantity="2"),
                _flow(sell_day, TxType.SELL, "150", quantity="1"),
            ],
        )

        result = await use_case.execute(_query())

        yesterday = date.today() - timedelta(days=1)
        assert result.points[0].date == buy_day
        assert result.points[-1].date == yesterday
        metrics = result.points[-1].metrics
        assert metrics.value == Dezimal(100)
        assert metrics.net_contributions == Dezimal(50)
        assert metrics.gain == Dezimal(50)

    @pytest.mark.asyncio
    async def test_replay_handover_to_snapshot_without_double_counting(self):
        buy_day = date(2024, 11, 1)
        snapshot_day = date(2025, 1, 3)
        use_case, _ = _build(
            [_snapshot(snapshot_day, "1", "250", cost_basis="100")],
            [_flow(buy_day, TxType.BUY, "100", quantity="1")],
        )

        result = await use_case.execute(_query())

        assert result.points[0].date == buy_day
        assert result.points[-1].date == snapshot_day
        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[buy_day].value == Dezimal(100)
        assert by_day[buy_day].gain == Dezimal(0)
        metrics = by_day[snapshot_day]
        assert metrics.value == Dezimal(250)
        assert metrics.net_contributions == Dezimal(100)
        assert metrics.gain == Dezimal(150)

    @pytest.mark.asyncio
    async def test_snapshot_anchored_identity_does_not_replay(self):
        first_day = date(2025, 1, 1)
        second_day = date(2025, 1, 2)
        use_case, _ = _build(
            [
                _snapshot(first_day, "1", "100", cost_basis="100"),
                _snapshot(second_day, "1", "110", cost_basis="100"),
            ],
            [_flow(first_day, TxType.BUY, "100", quantity="1")],
        )

        result = await use_case.execute(_query())

        assert [point.date for point in result.points] == [first_day, second_day]
        assert result.quality == GainsQuality.COMPLETE

    @pytest.mark.asyncio
    async def test_replayed_days_carry_book_cost_basis(self):
        buy_day = date(2024, 11, 1)
        snapshot_day = date(2025, 1, 3)
        use_case, _ = _build(
            [_snapshot(snapshot_day, "1", "250", cost_basis="100")],
            [_flow(buy_day, TxType.BUY, "100", quantity="1")],
        )

        result = await use_case.execute(_query())

        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[buy_day].cost_basis == Dezimal(100)
        assert by_day[date(2025, 1, 2)].cost_basis == Dezimal(100)
        assert by_day[snapshot_day].cost_basis == Dezimal(100)

    @pytest.mark.asyncio
    async def test_handover_reconciles_replay_book_with_stored_cost_basis(self):
        buy_day = date(2024, 11, 1)
        snapshot_day = date(2025, 1, 3)
        use_case, _ = _build(
            [_snapshot(snapshot_day, "1", "250", cost_basis="80")],
            [_flow(buy_day, TxType.BUY, "100", quantity="1")],
        )

        result = await use_case.execute(_query())

        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[snapshot_day].value == Dezimal(250)
        assert by_day[snapshot_day].net_contributions == Dezimal(80)
        assert by_day[snapshot_day].gain == Dezimal(170)

    @pytest.mark.asyncio
    async def test_replay_uses_historical_prices_when_available(self):
        from domain.instrument_history import InstrumentPricePoint

        buy_day = date(2024, 11, 1)
        later_day = date(2024, 11, 3)
        port = AsyncMock(spec=GainsTimelinePort)
        port.get_data_version.return_value = "1"
        port.get_asset_snapshots.return_value = []
        port.get_flows.return_value = [
            GainsFlow(
                holder="wallet",
                product_type=ProductType.FUND,
                asset_key="IE00TEST",
                moment=datetime(buy_day.year, buy_day.month, buy_day.day, 12),
                amount=Dezimal(100),
                currency="EUR",
                quantity=Dezimal(2),
                transaction_type=TxType.BUY,
            )
        ]
        port.get_settlements.return_value = []

        exchange = AsyncMock()
        exchange.get.return_value = {}
        entity = AsyncMock()
        entity.get_disabled_entities.return_value = []
        entity.get_all.return_value = []
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None

        history_storage = AsyncMock()
        history_storage.is_no_result.return_value = False
        history_storage.get_history.return_value = [
            InstrumentPricePoint(date=buy_day, price=Dezimal(50), currency="EUR"),
            InstrumentPricePoint(date=later_day, price=Dezimal(60), currency="EUR"),
        ]
        history_storage.get_covered_range.return_value = (buy_day, later_day)
        history_storage.get_resolved_symbol.return_value = None
        history_provider = AsyncMock()
        use_case = GetGainsTimelineImpl(
            port,
            exchange,
            entity,
            metal,
            history_provider,
            history_storage,
        )

        result = await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.FUND)],
                entities=[uuid4()],
            )
        )

        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[buy_day].value == Dezimal(100)
        assert by_day[buy_day].gain == Dezimal(0)
        assert by_day[later_day].value == Dezimal(120)
        assert by_day[later_day].gain == Dezimal(20)
        history_provider.get_history.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fetches_and_persists_history_when_storage_empty(self):
        from domain.instrument_history import InstrumentPricePoint

        buy_day = date(2024, 11, 1)
        port = AsyncMock(spec=GainsTimelinePort)
        port.get_data_version.return_value = "1"
        port.get_asset_snapshots.return_value = []
        port.get_flows.return_value = [
            GainsFlow(
                holder="wallet",
                product_type=ProductType.FUND,
                asset_key="IE00TEST",
                moment=datetime(buy_day.year, buy_day.month, buy_day.day, 12),
                amount=Dezimal(100),
                currency="EUR",
                quantity=Dezimal(2),
                transaction_type=TxType.BUY,
            )
        ]
        port.get_settlements.return_value = []
        exchange = AsyncMock()
        exchange.get.return_value = {}
        entity = AsyncMock()
        entity.get_disabled_entities.return_value = []
        entity.get_all.return_value = []
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None
        history_storage = AsyncMock()
        history_storage.is_no_result.return_value = False
        history_storage.get_history.return_value = []
        history_storage.get_covered_range.return_value = None
        history_storage.get_resolved_symbol.return_value = None
        history_provider = AsyncMock()
        history_provider.get_history.return_value = (
            [InstrumentPricePoint(date=buy_day, price=Dezimal(50), currency="EUR")],
            "IE00TEST.F",
            "yfinance",
        )
        use_case = GetGainsTimelineImpl(
            port, exchange, entity, metal, history_provider, history_storage
        )

        await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.FUND)],
                entities=[uuid4()],
            )
        )

        history_provider.get_history.assert_awaited_once()
        history_storage.upsert.assert_awaited_once()
        _, kwargs = history_storage.upsert.call_args
        assert kwargs["source"] == "yfinance"
        history_storage.save_resolved_symbol.assert_awaited_once_with(
            "IE00TEST", "IE00TEST.F", source="yfinance"
        )

    @pytest.mark.asyncio
    async def test_etf_typed_snapshot_classifies_stock_etf_as_etf(self):
        from domain.instrument_history import InstrumentPricePoint

        buy_day = date(2024, 11, 1)
        snapshot_day = date(2024, 11, 2)
        port = AsyncMock(spec=GainsTimelinePort)
        port.get_data_version.return_value = "1"
        port.get_asset_snapshots.return_value = [
            AssetSnapshot(
                holder="broker",
                moment=datetime(
                    snapshot_day.year, snapshot_day.month, snapshot_day.day, 12
                ),
                valuations=[
                    AssetValuation(
                        product_type=ProductType.STOCK_ETF,
                        asset_key="IE00B4ND3602",
                        currency="EUR",
                        quantity=Dezimal(2),
                        market_value=Dezimal(120),
                        equity_type=EquityType.ETF,
                    )
                ],
            )
        ]
        port.get_flows.return_value = [
            GainsFlow(
                holder="broker",
                product_type=ProductType.STOCK_ETF,
                asset_key="IE00B4ND3602",
                moment=datetime(buy_day.year, buy_day.month, buy_day.day, 12),
                amount=Dezimal(100),
                currency="EUR",
                quantity=Dezimal(2),
                transaction_type=TxType.BUY,
            )
        ]
        port.get_settlements.return_value = []
        exchange = AsyncMock()
        exchange.get.return_value = {}
        entity = AsyncMock()
        entity.get_disabled_entities.return_value = []
        entity.get_all.return_value = []
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None
        history_storage = AsyncMock()
        history_storage.is_no_result.return_value = False
        history_storage.get_history.return_value = []
        history_storage.get_covered_range.return_value = None
        history_storage.get_resolved_symbol.return_value = None
        history_provider = AsyncMock()
        history_provider.get_history.return_value = (
            [InstrumentPricePoint(date=buy_day, price=Dezimal(50), currency="EUR")],
            "IE00B4ND3602",
            "justetf",
        )
        use_case = GetGainsTimelineImpl(
            port, exchange, entity, metal, history_provider, history_storage
        )

        await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.STOCK_ETF)],
                entities=[uuid4()],
            )
        )

        request = history_provider.get_history.await_args.args[0]
        assert request.type == InstrumentType.ETF

    @pytest.mark.asyncio
    async def test_marks_empty_tail_of_successful_fetch(self):
        from domain.instrument_history import InstrumentPricePoint

        buy_day = date(2024, 1, 2)
        last_priced_day = date(2024, 1, 5)
        sell_day = date(2024, 1, 10)
        port = AsyncMock(spec=GainsTimelinePort)
        port.get_data_version.return_value = "1"
        port.get_asset_snapshots.return_value = []
        port.get_flows.return_value = [
            GainsFlow(
                holder="wallet",
                product_type=ProductType.FUND,
                asset_key="IE00TEST",
                moment=datetime(buy_day.year, buy_day.month, buy_day.day, 12),
                amount=Dezimal(100),
                currency="EUR",
                quantity=Dezimal(2),
                transaction_type=TxType.BUY,
            ),
            GainsFlow(
                holder="wallet",
                product_type=ProductType.FUND,
                asset_key="IE00TEST",
                moment=datetime(sell_day.year, sell_day.month, sell_day.day, 12),
                amount=Dezimal(110),
                currency="EUR",
                quantity=Dezimal(2),
                transaction_type=TxType.SELL,
            ),
        ]
        port.get_settlements.return_value = []
        exchange = AsyncMock()
        exchange.get.return_value = {}
        entity = AsyncMock()
        entity.get_disabled_entities.return_value = []
        entity.get_all.return_value = []
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None
        history_storage = AsyncMock()
        history_storage.is_no_result.return_value = False
        history_storage.get_history.return_value = []
        history_storage.get_covered_range.return_value = None
        history_storage.get_resolved_symbol.return_value = None
        history_storage.get_empty_gap_days.return_value = set()
        history_provider = AsyncMock()
        history_provider.get_history.return_value = (
            [
                InstrumentPricePoint(
                    date=last_priced_day, price=Dezimal(50), currency="EUR"
                )
            ],
            "efb8b08c",
            "finect",
        )
        use_case = GetGainsTimelineImpl(
            port, exchange, entity, metal, history_provider, history_storage
        )

        await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.FUND)],
                entities=[uuid4()],
                from_date=buy_day,
                to_date=sell_day,
            )
        )

        marked = [
            day
            for call in history_storage.mark_empty_gap_days.await_args_list
            for day in call.args[1]
        ]
        assert marked == [
            date(2024, 1, 6),
            date(2024, 1, 7),
            date(2024, 1, 8),
            date(2024, 1, 9),
            date(2024, 1, 10),
        ]

    @pytest.mark.asyncio
    async def test_does_not_blacklist_recent_unpublished_tail(self):
        from domain.instrument_history import InstrumentPricePoint

        today = date.today()
        buy_day = today - timedelta(days=30)
        last_priced_day = today - timedelta(days=4)
        port = AsyncMock(spec=GainsTimelinePort)
        port.get_data_version.return_value = "1"
        port.get_asset_snapshots.return_value = []
        port.get_flows.return_value = [
            GainsFlow(
                holder="wallet",
                product_type=ProductType.FUND,
                asset_key="IE00TEST",
                moment=datetime(buy_day.year, buy_day.month, buy_day.day, 12),
                amount=Dezimal(100),
                currency="EUR",
                quantity=Dezimal(2),
                transaction_type=TxType.BUY,
            )
        ]
        port.get_settlements.return_value = []
        exchange = AsyncMock()
        exchange.get.return_value = {}
        entity = AsyncMock()
        entity.get_disabled_entities.return_value = []
        entity.get_all.return_value = []
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None
        history_storage = AsyncMock()
        history_storage.is_no_result.return_value = False
        history_storage.get_history.return_value = []
        history_storage.get_covered_range.return_value = None
        history_storage.get_resolved_symbol.return_value = None
        history_storage.get_empty_gap_days.return_value = set()
        history_provider = AsyncMock()
        history_provider.get_history.return_value = (
            [
                InstrumentPricePoint(
                    date=last_priced_day, price=Dezimal(50), currency="EUR"
                )
            ],
            "efb8b08c",
            "finect",
        )
        use_case = GetGainsTimelineImpl(
            port, exchange, entity, metal, history_provider, history_storage
        )

        await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.FUND)],
                entities=[uuid4()],
            )
        )

        marked = [
            day
            for call in history_storage.mark_empty_gap_days.await_args_list
            for day in call.args[1]
        ]
        assert marked == []

    @pytest.mark.asyncio
    async def test_mutual_funds_never_check_splits(self):
        from domain.instrument_history import InstrumentPricePoint

        buy_day = date(2024, 11, 1)
        port = AsyncMock(spec=GainsTimelinePort)
        port.get_data_version.return_value = "1"
        port.get_asset_snapshots.return_value = []
        port.get_flows.return_value = [
            GainsFlow(
                holder="wallet",
                product_type=ProductType.FUND,
                asset_key="IE00BYX5NX33",
                moment=datetime(buy_day.year, buy_day.month, buy_day.day, 12),
                amount=Dezimal(100),
                currency="EUR",
                quantity=Dezimal(2),
                transaction_type=TxType.BUY,
            )
        ]
        port.get_settlements.return_value = []
        exchange = AsyncMock()
        exchange.get.return_value = {}
        entity = AsyncMock()
        entity.get_disabled_entities.return_value = []
        entity.get_all.return_value = []
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None
        history_storage = AsyncMock()
        history_storage.is_no_result.return_value = False
        history_storage.get_history.return_value = [
            InstrumentPricePoint(date=buy_day, price=Dezimal(50), currency="EUR")
        ]
        history_storage.get_covered_range.return_value = (buy_day, buy_day)
        history_storage.get_resolved_symbol.return_value = ("efb8b08c", "finect")
        history_storage.is_splits_checked.return_value = False
        history_provider = AsyncMock()
        use_case = GetGainsTimelineImpl(
            port, exchange, entity, metal, history_provider, history_storage
        )

        await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.FUND)],
                entities=[uuid4()],
            )
        )

        history_provider.get_splits.assert_not_awaited()
        history_storage.is_splits_checked.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_replay_scales_quantity_for_post_acquisition_split(self):
        from domain.instrument_history import InstrumentPricePoint, InstrumentSplit

        buy_day = date(2025, 2, 13)
        later_day = date(2025, 2, 14)
        split_day = date(2025, 6, 19)
        port = AsyncMock(spec=GainsTimelinePort)
        port.get_data_version.return_value = "1"
        port.get_asset_snapshots.return_value = []
        port.get_flows.return_value = [
            GainsFlow(
                holder="wallet",
                product_type=ProductType.STOCK_ETF,
                asset_key="ES0105046009",
                moment=datetime(buy_day.year, buy_day.month, buy_day.day, 12),
                amount=Dezimal(1094),
                currency="EUR",
                quantity=Dezimal(5),
                transaction_type=TxType.BUY,
                name="Aena",
            )
        ]
        port.get_settlements.return_value = []

        exchange = AsyncMock()
        exchange.get.return_value = {}
        entity = AsyncMock()
        entity.get_disabled_entities.return_value = []
        entity.get_all.return_value = []
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None

        history_storage = AsyncMock()
        history_storage.is_no_result.return_value = False
        history_storage.get_history.return_value = [
            InstrumentPricePoint(date=buy_day, price=Dezimal("22.02"), currency="EUR"),
            InstrumentPricePoint(
                date=later_day, price=Dezimal("22.02"), currency="EUR"
            ),
        ]
        history_storage.get_covered_range.return_value = (buy_day, later_day)
        history_storage.get_resolved_symbol.return_value = ("AENA.MC", "yfinance")
        history_storage.is_splits_checked.return_value = False
        history_provider = AsyncMock()
        history_provider.get_splits.return_value = [
            InstrumentSplit(date=split_day, ratio=Dezimal(10))
        ]
        use_case = GetGainsTimelineImpl(
            port, exchange, entity, metal, history_provider, history_storage
        )

        result = await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.STOCK_ETF)],
                entities=[uuid4()],
                from_date=buy_day,
                to_date=later_day,
            )
        )

        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[buy_day].value == Dezimal("1101.00")
        assert by_day[buy_day].gain == Dezimal("1101.00") - Dezimal(1094)
        history_provider.get_splits.assert_awaited()

    @pytest.mark.asyncio
    async def test_replay_normalizes_mixed_pre_post_split_buys(self):
        from domain.instrument_history import InstrumentPricePoint, InstrumentSplit

        port = AsyncMock(spec=GainsTimelinePort)
        port.get_data_version.return_value = "1"
        port.get_asset_snapshots.return_value = []
        port.get_flows.return_value = [
            GainsFlow(
                holder="wallet",
                product_type=ProductType.STOCK_ETF,
                asset_key="ES0105046009",
                moment=datetime(2025, 2, 13, 12),
                amount=Dezimal(1094),
                currency="EUR",
                quantity=Dezimal(5),
                transaction_type=TxType.BUY,
                name="Aena",
            ),
            GainsFlow(
                holder="wallet",
                product_type=ProductType.STOCK_ETF,
                asset_key="ES0105046009",
                moment=datetime(2025, 7, 1, 12),
                amount=Dezimal(220),
                currency="EUR",
                quantity=Dezimal(10),
                transaction_type=TxType.BUY,
                name="Aena",
            ),
        ]
        port.get_settlements.return_value = []

        exchange = AsyncMock()
        exchange.get.return_value = {}
        entity = AsyncMock()
        entity.get_disabled_entities.return_value = []
        entity.get_all.return_value = []
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None

        history_storage = AsyncMock()
        history_storage.is_no_result.return_value = False
        history_storage.get_history.return_value = [
            InstrumentPricePoint(
                date=date(2025, 2, 13), price=Dezimal("22.02"), currency="EUR"
            ),
            InstrumentPricePoint(
                date=date(2025, 7, 1), price=Dezimal("23.00"), currency="EUR"
            ),
        ]
        history_storage.get_covered_range.return_value = (
            date(2025, 2, 13),
            date(2025, 7, 1),
        )
        history_storage.get_resolved_symbol.return_value = ("AENA.MC", "yfinance")
        history_storage.is_splits_checked.return_value = False
        history_provider = AsyncMock()
        history_provider.get_splits.return_value = [
            InstrumentSplit(date=date(2025, 6, 19), ratio=Dezimal(10))
        ]
        use_case = GetGainsTimelineImpl(
            port, exchange, entity, metal, history_provider, history_storage
        )

        result = await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.STOCK_ETF)],
                entities=[uuid4()],
                from_date=date(2025, 2, 13),
                to_date=date(2025, 7, 1),
            )
        )

        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[date(2025, 7, 1)].value == Dezimal("60") * Dezimal("23.00")
        assert by_day[date(2025, 7, 1)].cost_basis == Dezimal(1094) + Dezimal(220)

    @pytest.mark.asyncio
    async def test_fund_transfer_carries_cost_without_new_contribution(self):
        first_snapshot = date(2025, 9, 15)
        transfer_day = date(2025, 9, 25)
        port = AsyncMock(spec=GainsTimelinePort)
        port.get_data_version.return_value = "1"
        port.get_asset_snapshots.return_value = [
            AssetSnapshot(
                holder="wallet",
                moment=datetime(2025, 9, 15, 12),
                valuations=[
                    AssetValuation(
                        product_type=ProductType.FUND,
                        asset_key="IE0032126645",
                        currency="EUR",
                        market_value=Dezimal("1.0158"),
                        cost_basis=Dezimal(2),
                        quantity=Dezimal("0.014921"),
                    )
                ],
            ),
            AssetSnapshot(
                holder="wallet",
                moment=datetime(2025, 9, 25, 12),
                valuations=[
                    AssetValuation(
                        product_type=ProductType.FUND,
                        asset_key="IE0007201266",
                        currency="EUR",
                        market_value=Dezimal("1.0027"),
                        cost_basis=Dezimal(2),
                        quantity=Dezimal("0.003156"),
                    )
                ],
            ),
        ]
        port.get_flows.return_value = [
            GainsFlow(
                holder="wallet",
                product_type=ProductType.FUND,
                asset_key="IE0032126645",
                moment=datetime(2025, 9, 8, 12),
                amount=Dezimal(1),
                currency="EUR",
                fees=Dezimal(1),
                quantity=Dezimal("0.014921"),
                transaction_type=TxType.BUY,
            )
        ]
        port.get_settlements.return_value = []

        exchange = AsyncMock()
        exchange.get.return_value = {}
        entity = AsyncMock()
        entity.get_disabled_entities.return_value = []
        entity.get_all.return_value = []
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None
        history_storage = AsyncMock()
        history_storage.is_no_result.return_value = False
        history_storage.get_history.return_value = []
        history_storage.get_covered_range.return_value = None
        history_storage.get_resolved_symbol.return_value = None
        history_storage.is_splits_checked.return_value = True
        history_provider = AsyncMock()
        history_provider.get_history.return_value = ([], None, None)
        use_case = GetGainsTimelineImpl(
            port, exchange, entity, metal, history_provider, history_storage
        )

        result = await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.FUND)],
                entities=[uuid4()],
                from_date=date(2025, 9, 1),
            )
        )

        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[first_snapshot].net_contributions == Dezimal(2)
        assert by_day[transfer_day].net_contributions == Dezimal(2)
        assert by_day[transfer_day].gain == Dezimal("1.0027") - Dezimal(2)
        assert by_day[transfer_day].gain - by_day[first_snapshot].gain == (
            Dezimal("1.0027") - Dezimal("1.0158")
        )

    @pytest.mark.asyncio
    async def test_switch_inherits_portfolio_onto_predecessor_buys(self):
        buy_day = date(2023, 8, 9)
        switch_day = date(2024, 2, 8)
        later_day = date(2024, 3, 1)

        def fund_flow(
            day, asset_key, transaction_type, amount, quantity, portfolio=None
        ):
            return GainsFlow(
                holder="indexa",
                product_type=ProductType.FUND,
                asset_key=asset_key,
                moment=datetime(day.year, day.month, day.day, 12),
                amount=Dezimal(amount),
                currency="EUR",
                quantity=Dezimal(quantity),
                portfolio_name=portfolio,
                transaction_type=transaction_type,
            )

        use_case, _ = _build(
            [
                AssetSnapshot(
                    holder="indexa",
                    moment=datetime(later_day.year, later_day.month, later_day.day, 12),
                    valuations=[
                        AssetValuation(
                            product_type=ProductType.FUND,
                            asset_key="IE00NEW",
                            currency="EUR",
                            market_value=Dezimal(1600),
                            cost_basis=Dezimal(1500),
                            quantity=Dezimal(15),
                            portfolio_name="AMNAYXT2",
                        )
                    ],
                )
            ],
            [
                fund_flow(buy_day, "IE00OLD", TxType.BUY, "1500", "15"),
                fund_flow(switch_day, "IE00OLD", TxType.SWITCH_FROM, "1500", "15"),
                fund_flow(
                    switch_day, "IE00NEW", TxType.SWITCH_TO, "1500", "15", "AMNAYXT2"
                ),
            ],
        )

        result = await use_case.execute(
            GainsTimelineQuery(
                assets=[
                    GainsAssetFilter(
                        product_type=ProductType.FUND, portfolio_names=["AMNAYXT2"]
                    )
                ],
                entities=[uuid4()],
                from_date=buy_day,
            )
        )

        assert result.points
        assert result.points[0].date == buy_day
        assert result.points[0].metrics.net_contributions == Dezimal(1500)
        assert use_case._port.get_flows.return_value[0].related_portfolios == [
            "AMNAYXT2"
        ]

    @pytest.mark.asyncio
    async def test_unpaired_transfer_in_does_not_create_false_loss(self):
        from domain.instrument_history import InstrumentPricePoint

        buy_day = date(2023, 8, 10)
        transfer_day = date(2023, 12, 22)
        later_day = date(2024, 3, 1)
        price = Dezimal("290")

        def fund_flow(day, transaction_type, amount, quantity, portfolio=None):
            return GainsFlow(
                holder="indexa",
                product_type=ProductType.FUND,
                asset_key="IE00OLD",
                moment=datetime(day.year, day.month, day.day, 12),
                amount=Dezimal(amount),
                currency="EUR",
                quantity=Dezimal(quantity),
                portfolio_name=portfolio,
                transaction_type=transaction_type,
            )

        port = AsyncMock(spec=GainsTimelinePort)
        port.get_data_version.return_value = "1"
        port.get_asset_snapshots.return_value = [
            AssetSnapshot(
                holder="indexa",
                moment=datetime(later_day.year, later_day.month, later_day.day, 12),
                valuations=[
                    AssetValuation(
                        product_type=ProductType.FUND,
                        asset_key="IE00OLD",
                        currency="EUR",
                        market_value=Dezimal("3190"),
                        cost_basis=Dezimal("3238.70"),
                        quantity=Dezimal("11"),
                        portfolio_name="AMNAYXT2",
                    )
                ],
            )
        ]
        port.get_flows.return_value = [
            fund_flow(buy_day, TxType.BUY, "600", "2"),
            fund_flow(transfer_day, TxType.TRANSFER_IN, "2638.70", "9.1"),
            fund_flow(date(2024, 2, 12), TxType.BUY, "87", "0.3", "AMNAYXT2"),
        ]
        port.get_settlements.return_value = []
        exchange = AsyncMock()
        exchange.get.return_value = {}
        entity = AsyncMock()
        entity.get_disabled_entities.return_value = []
        entity.get_all.return_value = []
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None
        history_storage = AsyncMock()
        history_storage.is_no_result.return_value = False
        history_storage.get_history.return_value = [
            InstrumentPricePoint(date=buy_day, price=price, currency="EUR"),
            InstrumentPricePoint(date=transfer_day, price=price, currency="EUR"),
        ]
        history_storage.get_covered_range.return_value = (buy_day, later_day)
        history_storage.get_resolved_symbol.return_value = None
        history_storage.is_splits_checked.return_value = True
        history_provider = AsyncMock()
        history_provider.get_history.return_value = ([], None, None)
        use_case = GetGainsTimelineImpl(
            port, exchange, entity, metal, history_provider, history_storage
        )

        result = await use_case.execute(
            GainsTimelineQuery(
                assets=[
                    GainsAssetFilter(
                        product_type=ProductType.FUND, portfolio_names=["AMNAYXT2"]
                    )
                ],
                entities=[uuid4()],
                from_date=buy_day,
            )
        )

        by_day = {point.date: point.metrics for point in result.points}
        transfer = by_day[transfer_day]
        assert transfer.net_contributions == Dezimal("3238.70")
        assert transfer.value == Dezimal("11.1") * price
        assert transfer.gain == transfer.value - Dezimal("3238.70")
        assert abs(transfer.gain) < Dezimal(30)

    @pytest.mark.asyncio
    async def test_isin_change_closes_book_on_merger_exit(self):
        # Liberbank ES0168675009 -> ES0168675090 (reverse split) -> swapped into
        # Unicaja and sold; the old ISIN never receives an outflow of its own.
        old_isin = "ES0168675009"
        new_isin = "ES0168675090"
        merged_isin = "ES0180907000"
        swap_day = date(2021, 8, 1)
        sell_day = date(2021, 10, 31)

        def stock_flow(day, asset, ttype, amount, quantity, name):
            return GainsFlow(
                holder="ing",
                product_type=ProductType.STOCK_ETF,
                asset_key=asset,
                moment=datetime(day.year, day.month, day.day, 12),
                amount=Dezimal(amount),
                currency="EUR",
                quantity=Dezimal(quantity),
                transaction_type=ttype,
                name=name,
            )

        use_case, _ = _build(
            [],
            [
                stock_flow(
                    date(2014, 3, 16), old_isin, TxType.BUY, "857", "1000", "LIBERBANK"
                ),
                stock_flow(
                    date(2014, 7, 21),
                    old_isin,
                    TxType.BUY,
                    "309.50",
                    "500",
                    "LIBERBANK",
                ),
                stock_flow(
                    date(2014, 8, 5), old_isin, TxType.BUY, "307.50", "500", "LIBERBANK"
                ),
                stock_flow(
                    date(2019, 5, 12),
                    new_isin,
                    TxType.DIVIDEND,
                    "4.93",
                    "681",
                    "LIBERBANK",
                ),
                stock_flow(
                    swap_day, new_isin, TxType.SWAP_FROM, "0", "681", "LIBERBANK"
                ),
                stock_flow(
                    swap_day, merged_isin, TxType.SWAP_TO, "0", "245", "UNICAJA"
                ),
                stock_flow(
                    sell_day, merged_isin, TxType.SELL, "232.63", "245", "UNICAJA"
                ),
            ],
        )

        result = await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.STOCK_ETF)],
                entities=[uuid4()],
            )
        )

        last = result.points[-1].metrics
        assert last.value == Dezimal(0)
        # 1474 invested, 232.63 back on the merged sale, 4.93 of dividends
        assert last.net_contributions == Dezimal("1236.44")
        assert last.gain == Dezimal("-1236.44")

        by_day = {point.date: point.metrics for point in result.points}
        # the swap carries the book onto the surviving ISIN instead of zeroing it
        assert by_day[swap_day].cost_basis == Dezimal("1474.00")

    @pytest.mark.asyncio
    async def test_foreign_currency_handover_does_not_shift_contributions(self):
        buy_day = date(2025, 1, 6)
        snapshot_day = date(2025, 9, 15)

        use_case, _ = _build(
            [
                AssetSnapshot(
                    holder="broker",
                    moment=datetime(
                        snapshot_day.year, snapshot_day.month, snapshot_day.day, 12
                    ),
                    valuations=[
                        AssetValuation(
                            product_type=ProductType.STOCK_ETF,
                            asset_key="US0378331005",
                            currency="USD",
                            market_value=Dezimal(12000),
                            cost_basis=Dezimal(10000),
                            quantity=Dezimal(100),
                        )
                    ],
                )
            ],
            [
                GainsFlow(
                    holder="broker",
                    product_type=ProductType.STOCK_ETF,
                    asset_key="US0378331005",
                    moment=datetime(buy_day.year, buy_day.month, buy_day.day, 12),
                    amount=Dezimal(10000),
                    currency="USD",
                    quantity=Dezimal(100),
                    transaction_type=TxType.BUY,
                )
            ],
            rates={"EUR": {"USD": Dezimal(2)}},
        )

        result = await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.STOCK_ETF)],
                entities=[uuid4()],
                base_currency="EUR",
            )
        )

        by_day = {point.date: point.metrics for point in result.points}
        before = by_day[snapshot_day - timedelta(days=1)]
        after = by_day[snapshot_day]
        # the stored cost matches the replayed book, so handover must not move it
        assert before.net_contributions == Dezimal(5000)
        assert after.net_contributions == Dezimal(5000)
        assert after.value == Dezimal(6000)
        assert after.gain == Dezimal(1000)

    @pytest.mark.asyncio
    async def test_dividends_before_any_holding_are_not_gains(self):
        dividend_day = date(2013, 12, 19)
        buy_day = date(2022, 6, 23)
        sell_day = date(2022, 9, 12)

        def stock_flow(day, ttype, amount, quantity):
            return GainsFlow(
                holder="ing",
                product_type=ProductType.STOCK_ETF,
                asset_key="ES0124244E34",
                moment=datetime(day.year, day.month, day.day, 12),
                amount=Dezimal(amount),
                currency="EUR",
                quantity=Dezimal(quantity),
                transaction_type=ttype,
                name="MAPFRE",
            )

        use_case, _ = _build(
            [],
            [
                stock_flow(dividend_day, TxType.DIVIDEND, "50.85", "1017"),
                stock_flow(date(2014, 1, 16), TxType.SELL, "1778.48", "517"),
                stock_flow(buy_day, TxType.BUY, "1489.50", "900"),
                stock_flow(sell_day, TxType.SELL, "1555.20", "900"),
            ],
        )

        result = await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.STOCK_ETF)],
                entities=[uuid4()],
            )
        )

        by_day = {point.date: point.metrics for point in result.points}
        # nothing was owned yet, so the dividend cannot show up as profit
        assert by_day[result.points[0].date].gain == Dezimal(0)
        assert by_day[result.points[0].date].net_contributions == Dezimal(0)
        last = result.points[-1].metrics
        assert last.value == Dezimal(0)
        assert last.gain == Dezimal("65.70")

    @pytest.mark.asyncio
    async def test_orphan_sell_does_not_count_as_gain(self):
        orphan_sell_day = date(2023, 6, 15)
        port = AsyncMock(spec=GainsTimelinePort)
        port.get_data_version.return_value = "1"
        port.get_asset_snapshots.return_value = []
        port.get_flows.return_value = [
            GainsFlow(
                holder="wallet",
                product_type=ProductType.STOCK_ETF,
                asset_key="ES0162600003",
                moment=datetime(2023, 2, 22, 12),
                amount=Dezimal(1440),
                currency="EUR",
                quantity=Dezimal(1600),
                transaction_type=TxType.BUY,
            ),
            GainsFlow(
                holder="wallet",
                product_type=ProductType.STOCK_ETF,
                asset_key="ES0162600003",
                moment=datetime(2023, 2, 22, 13),
                amount=Dezimal(1488),
                currency="EUR",
                quantity=Dezimal(1600),
                transaction_type=TxType.SELL,
            ),
            GainsFlow(
                holder="wallet",
                product_type=ProductType.STOCK_ETF,
                asset_key="ES0162600003",
                moment=datetime(2023, 6, 15, 12),
                amount=Dezimal(2228),
                currency="EUR",
                quantity=Dezimal(3184),
                transaction_type=TxType.SELL,
            ),
        ]
        port.get_settlements.return_value = []

        exchange = AsyncMock()
        exchange.get.return_value = {}
        entity = AsyncMock()
        entity.get_disabled_entities.return_value = []
        entity.get_all.return_value = []
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None
        history_storage = AsyncMock()
        history_storage.is_no_result.return_value = False
        history_storage.get_history.return_value = []
        history_storage.get_covered_range.return_value = None
        history_storage.get_resolved_symbol.return_value = None
        history_storage.get_empty_gap_days.return_value = set()
        history_storage.is_splits_checked.return_value = True
        history_provider = AsyncMock()
        history_provider.get_history.return_value = ([], None, None)
        use_case = GetGainsTimelineImpl(
            port, exchange, entity, metal, history_provider, history_storage
        )

        result = await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.STOCK_ETF)],
                entities=[uuid4()],
                from_date=date(2023, 1, 1),
            )
        )

        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[orphan_sell_day].gain == by_day[date(2023, 2, 22)].gain
        assert any("no matching buy" in warning for warning in result.warnings)

    @pytest.mark.asyncio
    async def test_skips_history_persist_when_provider_returns_nothing(self):
        buy_day = date(2024, 11, 1)
        port = AsyncMock(spec=GainsTimelinePort)
        port.get_data_version.return_value = "1"
        port.get_asset_snapshots.return_value = []
        port.get_flows.return_value = [
            GainsFlow(
                holder="wallet",
                product_type=ProductType.FUND,
                asset_key="IE00TEST",
                moment=datetime(buy_day.year, buy_day.month, buy_day.day, 12),
                amount=Dezimal(100),
                currency="EUR",
                quantity=Dezimal(2),
                transaction_type=TxType.BUY,
            )
        ]
        port.get_settlements.return_value = []
        exchange = AsyncMock()
        exchange.get.return_value = {}
        entity = AsyncMock()
        entity.get_disabled_entities.return_value = []
        entity.get_all.return_value = []
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None
        history_storage = AsyncMock()
        history_storage.is_no_result.return_value = False
        history_storage.get_history.return_value = []
        history_storage.get_covered_range.return_value = None
        history_storage.get_resolved_symbol.return_value = None
        history_provider = AsyncMock()
        history_provider.get_history.return_value = ([], None, None)
        use_case = GetGainsTimelineImpl(
            port, exchange, entity, metal, history_provider, history_storage
        )

        await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.FUND)],
                entities=[uuid4()],
            )
        )

        history_storage.upsert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_closed_position_before_range_is_not_fetched(self):
        port = AsyncMock(spec=GainsTimelinePort)
        port.get_data_version.return_value = "1"
        port.get_asset_snapshots.return_value = []
        port.get_flows.return_value = [
            GainsFlow(
                holder="wallet",
                product_type=ProductType.STOCK_ETF,
                asset_key="ES0113900J37",
                moment=datetime(2020, 3, 13, 12),
                amount=Dezimal(2313),
                currency="EUR",
                quantity=Dezimal(1000),
                transaction_type=TxType.BUY,
            ),
            GainsFlow(
                holder="wallet",
                product_type=ProductType.STOCK_ETF,
                asset_key="ES0113900J37",
                moment=datetime(2020, 12, 4, 12),
                amount=Dezimal(2715),
                currency="EUR",
                quantity=Dezimal(1000),
                transaction_type=TxType.SELL,
            ),
        ]
        port.get_settlements.return_value = []
        exchange = AsyncMock()
        exchange.get.return_value = {}
        entity = AsyncMock()
        entity.get_disabled_entities.return_value = []
        entity.get_all.return_value = []
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None
        history_storage = AsyncMock()
        history_storage.is_no_result.return_value = False
        history_storage.get_history.return_value = []
        history_storage.get_covered_range.return_value = None
        history_storage.get_resolved_symbol.return_value = None
        history_storage.get_empty_gap_days.return_value = set()
        history_provider = AsyncMock()
        history_provider.get_history.return_value = ([], None, None)
        use_case = GetGainsTimelineImpl(
            port, exchange, entity, metal, history_provider, history_storage
        )

        await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.STOCK_ETF)],
                entities=[uuid4()],
                from_date=date(2026, 1, 1),
            )
        )

        history_provider.get_history.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_result_asset_is_not_refetched(self):
        port = AsyncMock(spec=GainsTimelinePort)
        port.get_data_version.return_value = "1"
        port.get_asset_snapshots.return_value = []
        port.get_flows.return_value = [
            GainsFlow(
                holder="wallet",
                product_type=ProductType.STOCK_ETF,
                asset_key="ES0168675009",
                moment=datetime(2024, 11, 1, 12),
                amount=Dezimal(100),
                currency="EUR",
                quantity=Dezimal(1),
                transaction_type=TxType.BUY,
            )
        ]
        port.get_settlements.return_value = []
        exchange = AsyncMock()
        exchange.get.return_value = {}
        entity = AsyncMock()
        entity.get_disabled_entities.return_value = []
        entity.get_all.return_value = []
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None
        history_storage = AsyncMock()
        history_storage.is_no_result.return_value = True
        history_storage.get_history.return_value = []
        history_storage.get_covered_range.return_value = None
        history_provider = AsyncMock()
        use_case = GetGainsTimelineImpl(
            port, exchange, entity, metal, history_provider, history_storage
        )

        await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.STOCK_ETF)],
                entities=[uuid4()],
            )
        )

        history_provider.get_history.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_history_fetch_scoped_to_asset_replay_window(self):
        from domain.instrument_history import InstrumentPricePoint

        buy_day = date(2024, 11, 1)
        sell_day = date(2024, 11, 10)
        port = AsyncMock(spec=GainsTimelinePort)
        port.get_data_version.return_value = "1"
        port.get_asset_snapshots.return_value = []
        port.get_flows.return_value = [
            GainsFlow(
                holder="wallet",
                product_type=ProductType.FUND,
                asset_key="IE00TEST",
                moment=datetime(buy_day.year, buy_day.month, buy_day.day, 12),
                amount=Dezimal(100),
                currency="EUR",
                quantity=Dezimal(2),
                transaction_type=TxType.BUY,
            ),
            GainsFlow(
                holder="wallet",
                product_type=ProductType.FUND,
                asset_key="IE00TEST",
                moment=datetime(sell_day.year, sell_day.month, sell_day.day, 12),
                amount=Dezimal(120),
                currency="EUR",
                quantity=Dezimal(2),
                transaction_type=TxType.SELL,
            ),
        ]
        port.get_settlements.return_value = []
        exchange = AsyncMock()
        exchange.get.return_value = {}
        entity = AsyncMock()
        entity.get_disabled_entities.return_value = []
        entity.get_all.return_value = []
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None
        history_storage = AsyncMock()
        history_storage.is_no_result.return_value = False
        history_storage.get_history.return_value = []
        history_storage.get_covered_range.return_value = None
        history_storage.get_resolved_symbol.return_value = None
        history_storage.get_empty_gap_days.return_value = set()
        history_provider = AsyncMock()
        history_provider.get_history.return_value = (
            [InstrumentPricePoint(date=buy_day, price=Dezimal(50), currency="EUR")],
            "IE00TEST.F",
            "yfinance",
        )
        use_case = GetGainsTimelineImpl(
            port, exchange, entity, metal, history_provider, history_storage
        )

        await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.FUND)],
                entities=[uuid4()],
                from_date=date(2022, 1, 1),
            )
        )

        call = history_provider.get_history.mock_calls[0]
        _, args, _ = call
        _, from_arg, to_arg = args[:3]
        assert from_arg == buy_day
        assert to_arg == sell_day + timedelta(days=1)

    @pytest.mark.asyncio
    async def test_history_request_routes_isin_vs_ticker(self):
        from domain.instrument import InstrumentType

        assert (
            GetGainsTimelineImpl._history_request(
                "IE00BYX5NX33", InstrumentType.MUTUAL_FUND
            ).isin
            == "IE00BYX5NX33"
        )
        assert (
            GetGainsTimelineImpl._history_request(
                "N5138", InstrumentType.MUTUAL_FUND
            ).ticker
            == "N5138"
        )
        assert (
            GetGainsTimelineImpl._history_request(
                "My Fund", InstrumentType.MUTUAL_FUND
            ).ticker
            == "My Fund"
        )

    @pytest.mark.asyncio
    async def test_partial_stored_coverage_fetches_only_missing_leading_gap(self):
        from domain.instrument_history import InstrumentPricePoint

        buy_day = date(2024, 11, 1)
        sell_day = date(2024, 11, 10)
        stored_start = date(2024, 11, 5)
        port = AsyncMock(spec=GainsTimelinePort)
        port.get_data_version.return_value = "1"
        port.get_asset_snapshots.return_value = []
        port.get_flows.return_value = [
            GainsFlow(
                holder="wallet",
                product_type=ProductType.FUND,
                asset_key="IE00TEST",
                moment=datetime(buy_day.year, buy_day.month, buy_day.day, 12),
                amount=Dezimal(100),
                currency="EUR",
                quantity=Dezimal(2),
                transaction_type=TxType.BUY,
            ),
            GainsFlow(
                holder="wallet",
                product_type=ProductType.FUND,
                asset_key="IE00TEST",
                moment=datetime(sell_day.year, sell_day.month, sell_day.day, 12),
                amount=Dezimal(120),
                currency="EUR",
                quantity=Dezimal(2),
                transaction_type=TxType.SELL,
            ),
        ]
        port.get_settlements.return_value = []
        exchange = AsyncMock()
        exchange.get.return_value = {}
        entity = AsyncMock()
        entity.get_disabled_entities.return_value = []
        entity.get_all.return_value = []
        metal = AsyncMock()
        metal.get_partial_historic_rates.return_value = None
        history_storage = AsyncMock()
        history_storage.is_no_result.return_value = False
        history_storage.get_history.return_value = [
            InstrumentPricePoint(date=stored_start, price=Dezimal(55), currency="EUR"),
            InstrumentPricePoint(date=sell_day, price=Dezimal(60), currency="EUR"),
        ]
        history_storage.get_covered_range.return_value = (stored_start, sell_day)
        history_storage.get_resolved_symbol.return_value = None
        history_provider = AsyncMock()
        history_provider.get_history.return_value = (
            [InstrumentPricePoint(date=buy_day, price=Dezimal(50), currency="EUR")],
            "IE00TEST.F",
            "yfinance",
        )
        use_case = GetGainsTimelineImpl(
            port, exchange, entity, metal, history_provider, history_storage
        )

        await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.FUND)],
                entities=[uuid4()],
            )
        )

        call = history_provider.get_history.mock_calls[0]
        _, args, _ = call
        _, from_arg, to_arg = args[:3]
        assert from_arg == buy_day
        assert to_arg == stored_start
        history_storage.upsert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handover_matches_when_portfolio_metadata_drifts(self):
        snapshot_day = date(2025, 1, 3)
        flow = GainsFlow(
            holder="wallet",
            product_type=ProductType.FUND,
            asset_key="IE00TEST",
            moment=datetime(2024, 11, 1, 12),
            amount=Dezimal(100),
            currency="EUR",
            quantity=Dezimal(1),
            transaction_type=TxType.SUBSCRIPTION,
            portfolio_name="Long-term",
        )
        valuation = AssetValuation(
            product_type=ProductType.FUND,
            asset_key="IE00TEST",
            currency="EUR",
            quantity=Dezimal(1),
            market_value=Dezimal(130),
            cost_basis=Dezimal(100),
            portfolio_name=None,
        )
        snapshot = AssetSnapshot(
            holder="wallet",
            moment=datetime(2025, 1, 3, 12),
            valuations=[valuation],
        )
        use_case, _ = _build([snapshot], [flow])
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.FUND)],
            entities=[uuid4()],
        )

        result = await use_case.execute(query)

        by_day = {point.date: point.metrics for point in result.points}
        assert by_day[snapshot_day].value == Dezimal(130)
        assert by_day[snapshot_day].gain == Dezimal(30)
        assert by_day[snapshot_day].net_contributions == Dezimal(100)


class TestGetGainsTimelineBoundedRange:
    @pytest.mark.asyncio
    async def test_range_gain_starts_at_zero_and_excludes_past_growth(self):
        first_day = date(2024, 1, 1)
        mid_day = date(2025, 1, 1)
        last_day = date(2025, 1, 3)
        use_case, port = _build(
            [
                _snapshot(first_day, "1", "100", cost_basis="100"),
                _snapshot(mid_day, "1", "150", cost_basis="100"),
                _snapshot(last_day, "1", "165", cost_basis="100"),
            ]
        )
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.CRYPTO)],
            entities=[uuid4()],
            from_date=mid_day,
        )

        result = await use_case.execute(query)

        by_day = {point.date: point.metrics for point in result.points}
        assert list(by_day) == [mid_day, date(2025, 1, 2), last_day]
        assert by_day[mid_day].value == Dezimal(150)
        assert by_day[mid_day].net_contributions == Dezimal(0)
        assert by_day[mid_day].gain == Dezimal(50)
        assert by_day[mid_day].index == Dezimal(100)
        assert by_day[last_day].gain == Dezimal(65)
        assert by_day[last_day].net_contributions == Dezimal(0)
        assert result.opening_value == Dezimal(100)

    @pytest.mark.asyncio
    async def test_pre_range_flows_do_not_count_as_range_flows(self):
        buy_day = date(2024, 1, 1)
        mid_day = date(2025, 1, 1)
        last_day = date(2025, 1, 3)
        use_case, _ = _build(
            [
                _snapshot(buy_day, "1", "100", cost_basis="100"),
                _snapshot(last_day, "2", "260", cost_basis="200"),
            ],
            [_flow(mid_day, TxType.BUY, "100", quantity="1")],
        )
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.CRYPTO)],
            entities=[uuid4()],
            from_date=mid_day,
        )

        result = await use_case.execute(query)

        metrics = result.points[-1].metrics
        assert metrics.value == Dezimal(260)
        assert metrics.net_contributions == Dezimal(100)
        assert metrics.gain == Dezimal(60)

    @pytest.mark.asyncio
    async def test_replay_builds_opening_value_before_range(self):
        buy_day = date(2024, 1, 1)
        range_start = date(2025, 1, 1)
        snapshot_day = date(2025, 6, 1)
        use_case, _ = _build(
            [_snapshot(snapshot_day, "1", "130", cost_basis="100")],
            [_flow(buy_day, TxType.BUY, "100", quantity="1")],
        )
        query = GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.CRYPTO)],
            entities=[uuid4()],
            from_date=range_start,
        )

        result = await use_case.execute(query)

        by_day = {point.date: point.metrics for point in result.points}
        assert result.points[0].date == range_start
        assert result.points[-1].date == snapshot_day
        assert by_day[range_start].value == Dezimal(100)
        assert by_day[range_start].gain == Dezimal(0)
        assert by_day[snapshot_day].gain == Dezimal(30)
        assert result.opening_value == Dezimal(100)

    @pytest.mark.asyncio
    async def test_bounded_ranges_have_separate_cache_entries(self):
        first_day = date(2025, 1, 1)
        use_case, port = _build([_snapshot(first_day, "1", "100", cost_basis="100")])

        await use_case.execute(_query())
        await use_case.execute(
            GainsTimelineQuery(
                assets=[GainsAssetFilter(product_type=ProductType.CRYPTO)],
                entities=[uuid4()],
                from_date=first_day,
            )
        )

        assert port.get_asset_snapshots.await_count == 2

    @pytest.mark.asyncio
    async def test_flow_days_apply_start_of_day_inflow_convention(self):
        first_day = date(2025, 1, 1)
        second_day = date(2025, 1, 2)
        use_case, _ = _build(
            [
                _snapshot(first_day, "1", "100", cost_basis="100"),
                _snapshot(second_day, "2", "205", cost_basis="200"),
            ],
            [_flow(second_day, TxType.BUY, "100", quantity="1")],
        )

        result = await use_case.execute(_query())

        metrics = result.points[-1].metrics
        assert metrics.period_return == Dezimal("0.025")
        assert metrics.index == Dezimal("102.5")

    @pytest.mark.asyncio
    async def test_computes_annualized_xirr_for_long_periods(self):
        first_day = date(2025, 1, 1)
        second_day = date(2026, 1, 1)
        use_case, _ = _build(
            [
                _snapshot(first_day, "1", "100", cost_basis="100"),
                _snapshot(second_day, "1", "110", cost_basis="100"),
            ]
        )

        result = await use_case.execute(_query())

        assert result.xirr is not None
        assert result.annualized_xirr is not None
        assert Dezimal("0.099") < result.annualized_xirr < Dezimal("0.101")

    @pytest.mark.asyncio
    async def test_annualized_xirr_omitted_for_short_periods(self):
        first_day = date(2025, 1, 1)
        second_day = date(2025, 1, 20)
        use_case, _ = _build(
            [
                _snapshot(first_day, "1", "100", cost_basis="100"),
                _snapshot(second_day, "1", "105", cost_basis="100"),
            ]
        )

        result = await use_case.execute(_query())

        assert result.xirr is not None
        assert result.annualized_xirr is None


class TestGetGainsTimelineSnapshotsMode:
    def _snapshots_query(self):
        return GainsTimelineQuery(
            assets=[GainsAssetFilter(product_type=ProductType.CRYPTO)],
            entities=[uuid4()],
            calculation_mode=GainsCalculationMode.SNAPSHOTS,
        )

    @pytest.mark.asyncio
    async def test_skips_flows_and_settlements_and_uses_book_basis(self):
        first_day = date(2025, 1, 1)
        second_day = date(2025, 1, 3)
        use_case, port = _build(
            [
                _snapshot(first_day, "1", "100", cost_basis="100"),
                _snapshot(second_day, "1", "130", cost_basis="100"),
            ],
            flows=[_flow(first_day, TxType.BUY, "100", quantity="1")],
        )

        result = await use_case.execute(self._snapshots_query())

        port.get_flows.assert_not_awaited()
        port.get_settlements.assert_not_awaited()
        assert result.method == GainsMethod.SNAPSHOT_BOOK_BASIS
        assert result.basis == GainsBasis.BOOK_BASIS
        assert result.quality == GainsQuality.COMPLETE
        assert result.basis_status == GainsBasisStatus.COMPLETE
        assert result.warnings == []
        assert result.not_applicable_reasons == []
        assert [point.date for point in result.points] == [
            first_day,
            date(2025, 1, 2),
            second_day,
        ]
        last = result.points[-1].metrics
        assert last.value == Dezimal(130)
        assert last.cost_basis == Dezimal(100)
        assert last.net_contributions == Dezimal(100)
        assert last.gain == Dezimal(30)
        assert last.period_return is None
        assert last.index is None

    @pytest.mark.asyncio
    async def test_hybrid_mode_keeps_value_contract(self):
        first_day = date(2025, 1, 1)
        use_case, _ = _build([_snapshot(first_day, "1", "100", cost_basis="100")])

        result = await use_case.execute(_query())

        assert result.method == GainsMethod.HYBRID_VALUE
        assert result.basis == GainsBasis.NET_CONTRIBUTIONS
        assert result.quality == GainsQuality.COMPLETE
        assert result.basis_status == GainsBasisStatus.NOT_APPLICABLE
        assert result.points[-1].metrics.index is not None

    @pytest.mark.asyncio
    async def test_missing_cost_basis_marks_gain_unavailable(self):
        first_day = date(2025, 1, 1)
        use_case, _ = _build([_snapshot(first_day, "1", "100")])

        result = await use_case.execute(self._snapshots_query())

        assert result.basis_status == GainsBasisStatus.UNKNOWN
        assert result.quality == GainsQuality.DEGRADED
        assert result.not_applicable_reasons == [
            "Gain versus cost basis unavailable: no cost basis recorded for "
            "the selected positions."
        ]
        metrics = result.points[-1].metrics
        assert metrics.value == Dezimal(100)
        assert metrics.cost_basis == Dezimal(0)
        assert metrics.gain is None

    @pytest.mark.asyncio
    async def test_partial_cost_basis_scopes_gain_to_covered_positions(self):
        snapshot = AssetSnapshot(
            holder="wallet",
            moment=datetime(2025, 1, 1, 12),
            valuations=[
                _valuation("1", "100", cost_basis="80"),
                AssetValuation(
                    product_type=ProductType.CRYPTO,
                    asset_key="ETH",
                    currency="EUR",
                    quantity=Dezimal(2),
                    market_value=Dezimal(50),
                ),
            ],
        )
        use_case, _ = _build([snapshot])

        result = await use_case.execute(self._snapshots_query())

        assert result.basis_status == GainsBasisStatus.PARTIAL_UNKNOWN
        assert result.quality == GainsQuality.DEGRADED
        assert result.warnings == [
            "Some positions have no recorded cost basis; gain covers only "
            "positions with a known basis."
        ]
        metrics = result.points[-1].metrics
        assert metrics.value == Dezimal(150)
        assert metrics.cost_basis == Dezimal(80)
        assert metrics.gain == Dezimal(20)

    @pytest.mark.asyncio
    async def test_snapshot_mode_has_separate_cache_entry(self):
        first_day = date(2025, 1, 1)
        use_case, port = _build([_snapshot(first_day, "1", "100", cost_basis="100")])

        await use_case.execute(_query())
        await use_case.execute(self._snapshots_query())

        assert port.get_asset_snapshots.await_count == 2
        assert port.get_flows.await_count == 1


class TestGetGainsTimelineHybridQuality:
    @pytest.mark.asyncio
    async def test_complete_when_flows_fully_explain_positions(self):
        first_day = date(2025, 1, 1)
        use_case, _ = _build(
            [_snapshot(first_day, "1", "100", cost_basis="120")],
            flows=[_flow(first_day, TxType.BUY, "120", quantity="1")],
        )

        result = await use_case.execute(_query())

        assert result.quality == GainsQuality.COMPLETE
        assert result.warnings == []

    @pytest.mark.asyncio
    async def test_estimated_when_flows_are_inferred_from_snapshots(self):
        first_day = date(2025, 1, 1)
        second_day = date(2025, 1, 2)
        use_case, _ = _build(
            [
                _snapshot(first_day, "1", "100"),
                _snapshot(second_day, "2", "260"),
            ]
        )

        result = await use_case.execute(_query())

        assert result.quality == GainsQuality.ESTIMATED
        assert result.warnings == [
            "Some flows were inferred from quantity or cost-basis changes; "
            "contributions and returns may be estimates."
        ]

    @pytest.mark.asyncio
    async def test_degraded_when_asset_disappears_without_flows(self):
        first_day = date(2025, 1, 1)
        use_case, _ = _build(
            [
                _snapshot(first_day, "1", "100", cost_basis="100"),
                AssetSnapshot(
                    holder="wallet",
                    moment=datetime(2025, 1, 2, 12),
                    valuations=[],
                ),
            ]
        )

        result = await use_case.execute(_query())

        assert result.quality == GainsQuality.DEGRADED
        assert result.warnings == [
            "Some flows could not be valued or reconciled; results may be incomplete."
        ]
        assert result.xirr is None
        assert result.not_applicable_reasons == [
            "IRR unavailable because an external flow amount or asset "
            "movement could not be valued."
        ]


class TestGetGainsTimelineXirr:
    @pytest.mark.asyncio
    async def test_computes_xirr_from_opening_and_ending_values(self):
        first_day = date(2025, 1, 1)
        second_day = date(2026, 1, 1)
        use_case, _ = _build(
            [
                _snapshot(first_day, "1", "100", cost_basis="100"),
                _snapshot(second_day, "1", "110", cost_basis="100"),
            ]
        )

        result = await use_case.execute(_query())

        assert result.xirr is not None
        assert Dezimal("0.099") < result.xirr < Dezimal("0.101")

    @pytest.mark.asyncio
    async def test_xirr_accounts_for_dated_flows(self):
        first_day = date(2025, 1, 1)
        mid_day = date(2025, 7, 2)
        end_day = date(2026, 1, 1)
        use_case, _ = _build(
            [
                _snapshot(first_day, "1", "100", cost_basis="100"),
                _snapshot(mid_day, "2", "200", cost_basis="200"),
                _snapshot(end_day, "2", "220", cost_basis="200"),
            ],
            flows=[_flow(mid_day, TxType.BUY, "100", quantity="1")],
        )

        result = await use_case.execute(_query())

        assert result.xirr is not None
        assert Dezimal("0.12") < result.xirr < Dezimal("0.15")

    @pytest.mark.asyncio
    async def test_xirr_unavailable_without_sign_change(self):
        second_day = date(2026, 1, 1)
        use_case, _ = _build(
            [
                AssetSnapshot(
                    holder="wallet",
                    moment=datetime(2025, 1, 1, 12),
                    valuations=[],
                ),
                _snapshot(second_day, "1", "0"),
            ]
        )

        result = await use_case.execute(_query())

        assert result.xirr is None
