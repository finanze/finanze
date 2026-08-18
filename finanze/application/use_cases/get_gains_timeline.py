import asyncio
import hashlib
import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from application.ports.entity_port import EntityPort
from application.ports.exchange_rate_storage import ExchangeRateStorage
from application.ports.gains_timeline_port import GainsTimelinePort
from application.ports.historic_metal_price_provider import HistoricMetalPriceProvider
from application.ports.instrument_history_provider import InstrumentHistoryProvider
from application.ports.instrument_price_history_port import InstrumentPriceHistoryPort
from dateutil.tz import tzlocal
from domain.commodity import (
    COMMODITY_HISTORIC_CUTOFF,
    CommodityType,
    to_troy_ounces,
)
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
    GainsFlowProvenance,
    GainsMethod,
    GainsMetrics,
    GainsQuality,
    GainsSettlement,
    GainsTimeline,
    GainsTimelinePoint,
    GainsTimelineQuery,
)
from domain.global_position import EquityType, ProductType
from domain.instrument import InstrumentDataRequest, InstrumentType
from domain.transactions import TxType
from domain.use_cases.get_gains_timeline import GetGainsTimeline

_FIXED_INCOME_TYPES = {
    ProductType.DEPOSIT,
    ProductType.FACTORING,
    ProductType.REAL_ESTATE_CF,
}
_INFLOW_TYPES = {
    TxType.BUY,
    TxType.RIGHT_ISSUE,
    TxType.SUBSCRIPTION,
    TxType.TRANSFER_IN,
    TxType.SWITCH_TO,
    TxType.SWAP_TO,
    TxType.INVESTMENT,
}
_OUTFLOW_TYPES = {
    TxType.SELL,
    TxType.RIGHT_SELL,
    TxType.TRANSFER_OUT,
    TxType.SWITCH_FROM,
    TxType.SWAP_FROM,
    TxType.REPAYMENT,
    TxType.INTEREST,
    TxType.DIVIDEND,
}
_POSITION_CHANGING_TYPES = _INFLOW_TYPES | {
    TxType.SELL,
    TxType.RIGHT_SELL,
    TxType.TRANSFER_OUT,
    TxType.SWITCH_FROM,
    TxType.SWAP_FROM,
}
_REPLAY_PRODUCT_TYPES = {
    ProductType.STOCK_ETF,
    ProductType.FUND,
    ProductType.CRYPTO,
}
_TRANSFER_OUT_TYPES = {
    TxType.TRANSFER_OUT,
    TxType.SWITCH_FROM,
    TxType.SWAP_FROM,
}
_TRANSFER_IN_TYPES = {
    TxType.TRANSFER_IN,
    TxType.SWITCH_TO,
    TxType.SWAP_TO,
}
_AssetIdentity = tuple[str, ProductType, str, str, str, str, str]
_HistoricRates = dict[CommodityType, Optional[HistoricMetalRates]]

# Only blacklist a fetch's empty tail once providers have had time to publish it.
_TAIL_SETTLE_DAYS = 7

# How long an unreconciled inflow is still considered money in flight.
_INFLOW_SETTLE_DAYS = 7


@dataclass
class _TransferTransition:
    source: _AssetIdentity
    target: _AssetIdentity
    target_required_quantity: Dezimal
    resolved: bool = False


@dataclass
class _ReplayPosition:
    quantity: Optional[Dezimal] = Dezimal(0)
    book_value: Dezimal = Dezimal(0)


class GetGainsTimelineImpl(GetGainsTimeline):
    # Entries are also validated against the data version, so they only go stale
    # against market prices refreshed for the same day.
    CACHE_TTL_SECONDS = 3600

    def __init__(
        self,
        gains_timeline_port: GainsTimelinePort,
        exchange_rate_storage: ExchangeRateStorage,
        entity_port: EntityPort,
        historic_metal_price_provider: HistoricMetalPriceProvider,
        instrument_history_provider: Optional[InstrumentHistoryProvider] = None,
        instrument_price_history: Optional[InstrumentPriceHistoryPort] = None,
    ):
        self._port = gains_timeline_port
        self._exchange_rate_storage = exchange_rate_storage
        self._entity_port = entity_port
        self._metal_price_provider = historic_metal_price_provider
        self._instrument_history_provider = instrument_history_provider
        self._instrument_price_history = instrument_price_history
        self._lock = asyncio.Lock()
        self._cache: dict[str, tuple[str, float, GainsTimeline]] = {}
        self._splits_by_key: dict[str, dict[date, Dezimal]] = {}
        self._log = logging.getLogger(__name__)

    async def execute(self, query: GainsTimelineQuery) -> GainsTimeline:
        entity_ids = await self._resolve_entity_ids(query)
        if not entity_ids:
            return self._empty(query)

        rates = await self._exchange_rate_storage.get()
        data_version = await self._port.get_data_version()
        now = time.monotonic()
        yesterday = datetime.now(tzlocal()).date() - timedelta(days=1)
        cache_key = self._cache_key(query, entity_ids, rates, yesterday)

        async with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None and cached[0] == data_version and cached[1] > now:
                return self._slice(cached[2], query)

            if query.calculation_mode == GainsCalculationMode.SNAPSHOTS:
                snapshots = await self._port.get_asset_snapshots(
                    query.assets, entity_ids
                )
                historic = await self._resolve_historic_rates(
                    snapshots, query, yesterday
                )
                timeline = self._calculate_snapshots(
                    query, snapshots, rates, historic, yesterday
                )
            else:
                snapshots, flows, settlements = await asyncio.gather(
                    self._port.get_asset_snapshots(
                        query.assets, entity_ids, from_date=query.from_date
                    ),
                    self._port.get_flows(query.assets, entity_ids),
                    self._port.get_settlements(query.assets, entity_ids),
                )
                historic = await self._resolve_historic_rates(
                    snapshots, query, yesterday
                )
                history_by_key = await self._load_replay_history(
                    query,
                    snapshots,
                    flows,
                    yesterday,
                    query.from_date,
                )
                timeline = self._calculate(
                    query,
                    snapshots,
                    flows,
                    settlements,
                    rates,
                    historic,
                    yesterday,
                    history_by_key,
                )
            self._cache[cache_key] = (
                data_version,
                now + self.CACHE_TTL_SECONDS,
                timeline,
            )
            return self._slice(timeline, query)

    @staticmethod
    def _empty(query: GainsTimelineQuery) -> GainsTimeline:
        if query.calculation_mode == GainsCalculationMode.SNAPSHOTS:
            return GainsTimeline(
                currency=query.base_currency,
                method=GainsMethod.SNAPSHOT_BOOK_BASIS,
                basis=GainsBasis.BOOK_BASIS,
            )
        return GainsTimeline(currency=query.base_currency)

    async def _resolve_entity_ids(self, query: GainsTimelineQuery) -> list[str]:
        disabled = {
            str(entity.id)
            for entity in await self._entity_port.get_disabled_entities()
            if entity.id is not None
        }
        if query.entities is not None:
            entity_ids = [str(entity_id) for entity_id in query.entities]
        else:
            entity_ids = [
                str(entity.id)
                for entity in await self._entity_port.get_all()
                if entity.id is not None
            ]
        return sorted(set(entity_ids) - disabled)

    async def _resolve_historic_rates(
        self,
        snapshots: list[AssetSnapshot],
        query: GainsTimelineQuery,
        yesterday: date,
    ) -> _HistoricRates:
        upper = min(query.to_date or yesterday, yesterday)
        commodity_types = sorted(
            {
                valuation.commodity_type
                for snapshot in snapshots
                if snapshot.moment.date() <= upper
                and snapshot.moment.date() < COMMODITY_HISTORIC_CUTOFF
                for valuation in snapshot.valuations
                if self._is_historically_revaluable(valuation)
                and self._matches(
                    valuation.product_type,
                    valuation.asset_key,
                    query.assets,
                    valuation.portfolio_name,
                    valuation.equity_type,
                    valuation.wallet_id,
                )
            },
            key=lambda commodity_type: commodity_type.value,
        )
        if not commodity_types:
            return {}
        rates = await asyncio.gather(
            *(
                self._metal_price_provider.get_partial_historic_rates(commodity_type)
                for commodity_type in commodity_types
            )
        )
        return dict(zip(commodity_types, rates))

    def _calculate(
        self,
        query: GainsTimelineQuery,
        snapshots: list[AssetSnapshot],
        flows: list[GainsFlow],
        settlements: list[GainsSettlement],
        rates,
        historic: _HistoricRates,
        yesterday: date,
        history_by_key: Optional[dict[str, dict[date, Dezimal]]] = None,
    ) -> GainsTimeline:
        upper = min(query.to_date or yesterday, yesterday)
        range_from = query.from_date
        bounded = range_from is not None
        history_by_key = history_by_key or {}

        snapshots = [
            snapshot for snapshot in snapshots if snapshot.moment.date() <= upper
        ]
        settlements = sorted(
            (
                settlement
                for settlement in settlements
                if settlement.moment.date() <= upper
                and self._matches(
                    settlement.product_type, settlement.asset_key, query.assets
                )
            ),
            key=lambda settlement: settlement.moment,
        )
        flows = sorted(
            (
                flow
                for flow in flows
                if flow.moment.date() <= upper
                and self._matches(
                    flow.product_type,
                    flow.asset_key,
                    query.assets,
                    flow.portfolio_name,
                    flow.equity_type,
                    flow.wallet_id,
                )
            ),
            key=lambda flow: flow.moment,
        )

        seed_snapshots: dict[str, AssetSnapshot] = {}
        snapshots_by_day: dict[date, list[AssetSnapshot]] = defaultdict(list)
        for snapshot in snapshots:
            snapshot_day = snapshot.moment.date()
            if bounded and snapshot_day < range_from:
                existing = seed_snapshots.get(snapshot.holder)
                if existing is None or existing.moment <= snapshot.moment:
                    seed_snapshots[snapshot.holder] = snapshot
            else:
                snapshots_by_day[snapshot_day].append(snapshot)

        days = set(snapshots_by_day)
        days.update(self._commodity_days(snapshots, query.assets, historic, yesterday))
        if query.accrue_fixed_income != FixedIncomeAccrual.NONE:
            days.update(self._fixed_income_days(snapshots, query.assets, yesterday))
        days.update(settlement.moment.date() for settlement in settlements)
        replay_windows, replay_flow_days = self._replay_windows(
            flows, snapshots, query, yesterday, range_from
        )
        days.update(replay_flow_days)
        if bounded:
            days = {day for day in days if day >= range_from}
            if days or seed_snapshots or replay_windows:
                days.add(range_from)
        if days:
            grid_start = min(days)
            grid_end = max(days)
            day = grid_start
            while day <= grid_end:
                days.add(day)
                day += timedelta(days=1)
        output_days = sorted(days)
        if not output_days:
            return GainsTimeline(currency=query.base_currency)

        internal_transfer_flow_ids = self._internal_transfer_flow_ids(flows)
        fund_transfer_costs, fund_transfer_sources = self._detect_fund_transfers(
            snapshots, flows
        )
        provenance: set[GainsFlowProvenance] = set()
        if internal_transfer_flow_ids:
            provenance.add(GainsFlowProvenance.TRANSFER_PAIR)
        if replay_windows:
            provenance.add(GainsFlowProvenance.REPLAYED_POSITIONS)
        known_fixed_income_interest_payments = (
            self._known_fixed_income_interest_payments(flows, query.accrue_fixed_income)
        )

        current: dict[str, dict[_AssetIdentity, AssetValuation]] = {}
        deleted_at: dict[str, date] = {}
        replay_positions: dict[_AssetIdentity, _ReplayPosition] = {}
        replay_ended: set[_AssetIdentity] = set()
        orphan_sell_flow_ids: set[int] = set()
        replay_identity_by_key: dict[
            tuple[str, ProductType, str, str, str], _AssetIdentity
        ] = {self._identity_key(identity): identity for identity in replay_windows}
        flow_index = 0
        settlement_index = 0
        opening_values: dict[_AssetIdentity, Dezimal] = {}
        seeded_opening_keys: set[tuple[str, ProductType, str, str, str]] = set()

        if bounded:
            for holder, snapshot in seed_snapshots.items():
                holder_assets: dict[_AssetIdentity, AssetValuation] = {}
                for valuation in snapshot.valuations:
                    if not self._matches(
                        valuation.product_type,
                        valuation.asset_key,
                        query.assets,
                        valuation.portfolio_name,
                        valuation.equity_type,
                        valuation.wallet_id,
                    ):
                        continue
                    identity = self._valuation_identity(holder, valuation)
                    holder_assets[identity] = valuation
                current[holder] = holder_assets
                if snapshot.holder_deleted_at is not None:
                    deleted_at[holder] = snapshot.holder_deleted_at
            while (
                flow_index < len(flows) and flows[flow_index].moment.date() < range_from
            ):
                flow = flows[flow_index]
                identity = self._flow_identity(flow)
                replay_identity = replay_identity_by_key.get(
                    self._identity_key(identity)
                )
                if (
                    replay_identity is not None
                    and replay_windows[replay_identity][0] <= flow.moment.date()
                ):
                    self._update_replay_position(
                        replay_positions, flow, identity=replay_identity
                    )
                flow_index += 1
            while (
                settlement_index < len(settlements)
                and settlements[settlement_index].moment.date() < range_from
            ):
                settlement_index += 1
            opening_assets = self._flatten(current)
            opening_keys = {self._identity_key(identity) for identity in opening_assets}
            for identity, position in replay_positions.items():
                if (
                    position.book_value > 0
                    and self._identity_key(identity) not in opening_keys
                ):
                    opening_assets[identity] = self._replay_valuation(
                        identity,
                        position,
                        range_from,
                        history_by_key,
                        rates,
                        query.base_currency,
                    )
            seeded_opening_keys.update(opening_keys)
            for identity, valuation in opening_assets.items():
                value = self._valuation_value(
                    identity,
                    valuation,
                    range_from,
                    query.accrue_fixed_income,
                    query.base_currency,
                    rates,
                    known_fixed_income_interest_payments,
                    defaultdict(set),
                    historic,
                )
                if value is not None:
                    opening_values[identity] = value

        previous_assets: dict[_AssetIdentity, AssetValuation] = {}
        previous_asset_values: dict[_AssetIdentity, Dezimal] = dict(opening_values)
        contributions: dict[_AssetIdentity, Dezimal] = defaultdict(lambda: Dezimal(0))
        previous_values: dict[ProductType, Dezimal] = defaultdict(lambda: Dezimal(0))
        indices: dict[ProductType, Dezimal] = defaultdict(lambda: Dezimal(100))
        opening_by_type = self._sum_by_type(opening_values)
        opening_total = sum(opening_by_type.values(), Dezimal(0))
        previous_total = Dezimal(0)
        total_index = Dezimal(100)
        if bounded:
            previous_values.update(opening_by_type)
            previous_total = opening_total
            previous_assets = self._flatten(current)
            previous_keys = {
                self._identity_key(identity) for identity in previous_assets
            }
            for identity, position in replay_positions.items():
                if (
                    position.book_value > 0
                    and self._identity_key(identity) not in previous_keys
                ):
                    previous_assets[identity] = self._replay_valuation(
                        identity,
                        position,
                        range_from,
                        history_by_key,
                        rates,
                        query.base_currency,
                    )
        daily_net_flows: list[tuple[date, Dezimal]] = []
        unreconciled_flows: dict[_AssetIdentity, list[GainsFlow]] = defaultdict(list)
        pending_market_flows: dict[_AssetIdentity, list[GainsFlow]] = defaultdict(list)
        pending_period_flows: dict[_AssetIdentity, Dezimal] = defaultdict(
            lambda: Dezimal(0)
        )
        pending_fixed_income_flows: dict[_AssetIdentity, list[GainsFlow]] = defaultdict(
            list
        )
        observed_fixed_income_assets: set[_AssetIdentity] = set()
        recognized_fixed_income_interest_days: dict[_AssetIdentity, set[date]] = (
            defaultdict(set)
        )
        pending_transfer_outs: list[GainsFlow] = []
        transfer_exit_sources: set[_AssetIdentity] = set()
        transfer_transitions: list[_TransferTransition] = []
        suppressed_transfer_sources: set[_AssetIdentity] = set()
        points: list[GainsTimelinePoint] = []

        for day in output_days:
            changed_holders: set[str] = set()
            replay_handover: set[_AssetIdentity] = set()
            replay_touched_today = False
            for snapshot in sorted(
                snapshots_by_day.get(day, []), key=lambda snapshot: snapshot.moment
            ):
                holder_assets: dict[_AssetIdentity, AssetValuation] = {}
                previous_holder_assets = current.get(snapshot.holder, {})
                for valuation in snapshot.valuations:
                    if not self._matches(
                        valuation.product_type,
                        valuation.asset_key,
                        query.assets,
                        valuation.portfolio_name,
                        valuation.equity_type,
                        valuation.wallet_id,
                    ):
                        continue
                    identity = self._valuation_identity(snapshot.holder, valuation)
                    replay_identity = replay_identity_by_key.get(
                        self._identity_key(identity)
                    )
                    if (
                        replay_identity is not None
                        and replay_identity not in replay_ended
                    ):
                        replay_ended.add(replay_identity)
                        replay_handover.add(identity)
                        unreconciled_flows.pop(replay_identity, None)
                    holder_assets[identity] = self._retain_fixed_income_terms(
                        previous_holder_assets.get(identity), valuation
                    )
                    if identity not in previous_holder_assets:
                        carried = fund_transfer_costs.get(self._identity_key(identity))
                        if carried is not None:
                            current_valuation = holder_assets[identity]
                            holder_assets[identity] = replace(
                                current_valuation, cost_basis=carried
                            )
                current[snapshot.holder] = holder_assets
                if snapshot.holder_deleted_at is not None:
                    deleted_at[snapshot.holder] = snapshot.holder_deleted_at
                changed_holders.add(snapshot.holder)

            for holder, holder_deleted_at in deleted_at.items():
                if day >= holder_deleted_at and current.get(holder):
                    current[holder] = {}
                    changed_holders.add(holder)

            period_flows: dict[_AssetIdentity, Dezimal] = defaultdict(
                lambda: Dezimal(0)
            )
            while flow_index < len(flows) and flows[flow_index].moment.date() <= day:
                flow = flows[flow_index]
                identity = self._flow_identity(flow)
                replay_identity = replay_identity_by_key.get(
                    self._identity_key(identity)
                )
                replay_active = (
                    replay_identity is not None
                    and replay_identity not in replay_ended
                    and replay_windows[replay_identity][0]
                    <= flow.moment.date()
                    <= replay_windows[replay_identity][1]
                )
                if replay_active:
                    self._update_replay_position(
                        replay_positions,
                        flow,
                        identity=replay_identity,
                        orphan_sell_flow_ids=orphan_sell_flow_ids,
                    )
                    replay_touched_today = True
                if flow.product_type in _FIXED_INCOME_TYPES:
                    pending_fixed_income_flows[identity].append(flow)
                elif id(flow) not in internal_transfer_flow_ids:
                    if replay_active:
                        self._record_flow(
                            flow,
                            identity,
                            period_flows,
                            contributions,
                            unreconciled_flows,
                            query.base_currency,
                            rates,
                            query.accrue_fixed_income,
                            provenance,
                            orphan_sell_flow_ids,
                        )
                    elif self._requires_market_position_observation(flow):
                        pending_market_flows[identity].append(flow)
                    else:
                        self._record_flow(
                            flow,
                            identity,
                            period_flows,
                            contributions,
                            unreconciled_flows,
                            query.base_currency,
                            rates,
                            query.accrue_fixed_income,
                            provenance,
                            orphan_sell_flow_ids,
                        )
                if flow.transaction_type in _INFLOW_TYPES:
                    transfer_exit_sources.discard(identity)
                    suppressed_transfer_sources.discard(identity)
                    pending_transfer_outs = [
                        outgoing
                        for outgoing in pending_transfer_outs
                        if self._flow_identity(outgoing) != identity
                    ]
                if self._is_full_transfer_exit(flow, previous_assets.get(identity)):
                    transfer_exit_sources.add(identity)
                    pending_transfer_outs.append(flow)
                elif flow.transaction_type in _TRANSFER_IN_TYPES:
                    outgoing = self._pop_matching_transfer_out(
                        pending_transfer_outs, flow
                    )
                    if outgoing is not None and flow.quantity is not None:
                        target_previous = previous_assets.get(identity)
                        target_quantity = (
                            target_previous.quantity
                            if target_previous is not None
                            and target_previous.quantity is not None
                            else Dezimal(0)
                        )
                        transfer_transitions.append(
                            _TransferTransition(
                                source=self._flow_identity(outgoing),
                                target=identity,
                                target_required_quantity=target_quantity
                                + flow.quantity,
                            )
                        )
                flow_index += 1

            settlement_identities: set[_AssetIdentity] = set()
            while (
                settlement_index < len(settlements)
                and settlements[settlement_index].moment.date() <= day
            ):
                settlement = settlements[settlement_index]
                identity = (
                    settlement.holder,
                    settlement.product_type,
                    settlement.asset_key,
                    settlement.currency,
                    "",
                    "",
                    "",
                )
                converted = self._convert(
                    -settlement.net_proceeds,
                    settlement.currency,
                    query.base_currency,
                    rates,
                )
                if converted is not None:
                    period_flows[identity] += converted
                    contributions[identity] += converted
                    provenance.add(GainsFlowProvenance.SETTLEMENT)
                else:
                    provenance.add(GainsFlowProvenance.UNKNOWN)
                current.get(settlement.holder, {}).pop(identity, None)
                settlement_identities.add(identity)
                settlement_index += 1

            current_assets = self._flatten(current)
            settled_replay: set[_AssetIdentity] = set()
            if settlement_identities:
                settled_keys = {
                    self._identity_key(identity) for identity in settlement_identities
                }
                for identity, position in replay_positions.items():
                    if (
                        identity not in replay_ended
                        and self._identity_key(identity) in settled_keys
                    ):
                        replay_ended.add(identity)
                        if position.book_value > 0:
                            settlement_value = self._convert(
                                position.book_value,
                                identity[3],
                                query.base_currency,
                                rates,
                            )
                            if settlement_value is not None:
                                period_flows[identity] -= settlement_value
                                contributions[identity] -= settlement_value
                                provenance.add(GainsFlowProvenance.SETTLEMENT)
                        settled_replay.add(identity)
            for identity in settled_replay:
                replay_positions.pop(identity, None)
            current_keys = {self._identity_key(identity) for identity in current_assets}
            for identity, position in replay_positions.items():
                if (
                    identity in replay_ended
                    or self._identity_key(identity) in current_keys
                ):
                    continue
                window = replay_windows.get(identity)
                if position.book_value <= 0 and (window is None or day > window[2]):
                    continue
                current_assets[identity] = self._replay_valuation(
                    identity, position, day, history_by_key, rates, query.base_currency
                )
            pending_transfer_targets = {
                transition.target
                for transition in transfer_transitions
                if not transition.resolved
            }
            newly_suppressed, resolved_transfer_targets = (
                self._resolve_transfer_transitions(transfer_transitions, current_assets)
            )
            suppressed_transfer_sources.update(newly_suppressed)
            current_assets = {
                identity: valuation
                for identity, valuation in current_assets.items()
                if identity not in suppressed_transfer_sources
            }
            observed_fixed_income_assets.update(
                identity
                for identity, valuation in current_assets.items()
                if valuation.product_type in _FIXED_INCOME_TYPES
            )
            recorded_fixed_income_flows = self._record_ready_fixed_income_flows(
                pending_fixed_income_flows,
                current_assets,
                period_flows,
                contributions,
                unreconciled_flows,
                previous_assets,
                observed_fixed_income_assets,
                query.base_currency,
                rates,
                query.accrue_fixed_income,
                provenance,
            )
            for flow in recorded_fixed_income_flows:
                if flow.transaction_type == TxType.INTEREST:
                    recognized_fixed_income_interest_days[
                        self._flow_identity(flow)
                    ].add(flow.moment.date())
            current_values = {
                identity: value
                for identity, valuation in current_assets.items()
                if (
                    value := self._valuation_value(
                        identity,
                        valuation,
                        day,
                        query.accrue_fixed_income,
                        query.base_currency,
                        rates,
                        known_fixed_income_interest_payments,
                        recognized_fixed_income_interest_days,
                        historic,
                    )
                )
                is not None
            }
            current_costs = {
                identity: value
                for identity, valuation in current_assets.items()
                if valuation.cost_basis is not None
                and (
                    value := self._convert(
                        valuation.cost_basis,
                        valuation.currency,
                        query.base_currency,
                        rates,
                    )
                )
                is not None
            }

            changed_identities = set(settlement_identities)
            for holder in changed_holders:
                changed_identities.update(
                    identity for identity in previous_assets if identity[0] == holder
                )
                changed_identities.update(
                    identity for identity in current_assets if identity[0] == holder
                )
            transfer_reconciliation_identities = (
                transfer_exit_sources
                | pending_transfer_targets
                | resolved_transfer_targets
                | newly_suppressed
            )
            changed_identities.difference_update(transfer_reconciliation_identities)
            for identity in transfer_reconciliation_identities:
                unreconciled_flows.pop(identity, None)
            unobserved_market_snapshot_identities = {
                identity
                for identity in changed_identities
                if identity in pending_market_flows
                and not self._market_position_change_is_observed(
                    previous_assets.get(identity),
                    current_assets.get(identity),
                )
            }
            has_only_unobserved_market_snapshot_changes = (
                bool(pending_market_flows)
                and bool(changed_holders)
                and not (changed_identities - unobserved_market_snapshot_identities)
            )
            self._record_observed_market_flows(
                pending_market_flows,
                changed_identities,
                previous_assets,
                current_assets,
                period_flows,
                contributions,
                unreconciled_flows,
                query.base_currency,
                rates,
                query.accrue_fixed_income,
                provenance,
                replay_keys={
                    self._identity_key(identity) for identity in replay_handover
                },
            )
            for identity in changed_identities:
                if identity in replay_handover:
                    replay_identity = replay_identity_by_key.get(
                        self._identity_key(identity)
                    )
                    replay_book = (
                        replay_positions[replay_identity].book_value
                        if replay_identity is not None
                        and replay_identity in replay_positions
                        else None
                    )
                    current_valuation = current_assets.get(identity)
                    if (
                        replay_book is not None
                        and replay_book > 0
                        and current_valuation is not None
                        and current_valuation.cost_basis is not None
                    ):
                        stored_cost = self._convert(
                            current_valuation.cost_basis,
                            current_valuation.currency,
                            query.base_currency,
                            rates,
                        )
                        baseline = (
                            opening_values.get(identity, Dezimal(0))
                            if self._identity_key(identity) in seeded_opening_keys
                            else Dezimal(0)
                        )
                        expected_book = replay_book + baseline
                        if stored_cost is not None and stored_cost != expected_book:
                            correction = stored_cost - expected_book
                            period_flows[identity] += correction
                            contributions[identity] += correction
                            provenance.add(
                                GainsFlowProvenance.NET_CONTRIBUTION_FALLBACK
                            )
                    unreconciled_flows.pop(identity, None)
                    continue
                identity_key = self._identity_key(identity)
                if (
                    identity_key in fund_transfer_sources
                    or identity_key in fund_transfer_costs
                ):
                    unreconciled_flows.pop(identity, None)
                    continue
                prior_keyed: dict[_AssetIdentity, Dezimal] = dict(previous_asset_values)
                current_keyed = dict(current_values)
                for key, value in previous_asset_values.items():
                    canonical = self._identity_key(key)
                    for candidate in current_values:
                        if self._identity_key(candidate) == canonical:
                            prior_keyed[candidate] = value
                inferred, inferred_provenance = self._inferred_flow(
                    identity,
                    previous_assets.get(identity),
                    current_assets.get(identity),
                    previous_values_by_asset=current_keyed,
                    prior_values_by_asset=prior_keyed,
                    flows=unreconciled_flows.get(identity, []),
                    has_settlement=identity in settlement_identities,
                    target_currency=query.base_currency,
                    rates=rates,
                )
                if inferred is not None:
                    period_flows[identity] += inferred
                    contributions[identity] += inferred
                    if inferred_provenance is not None:
                        provenance.add(inferred_provenance)
                unreconciled_flows.pop(identity, None)

            for identity, value in period_flows.items():
                pending_period_flows[identity] += value

            day_flow = sum(period_flows.values(), Dezimal(0))
            if day_flow != 0:
                daily_net_flows.append((day, day_flow))

            replay_window_open = any(
                window[0] <= day <= window[2] and identity not in replay_ended
                for identity, window in replay_windows.items()
            )
            has_unobserved_inflow = self._has_unobserved_inflow(
                unreconciled_flows, pending_fixed_income_flows
            )
            has_inflight_inflow = self._has_unobserved_inflow(
                unreconciled_flows,
                pending_fixed_income_flows,
                day - timedelta(days=_INFLOW_SETTLE_DAYS),
            )
            should_emit = not has_only_unobserved_market_snapshot_changes and (
                bool(current_values)
                or bool(settlement_identities)
                or replay_touched_today
                or replay_window_open
                # hold the series flat while nothing is invested, unless money is
                # in flight to a position we haven't seen in a snapshot yet
                or (bool(points) and not has_inflight_inflow)
                or (
                    bool(previous_asset_values)
                    and bool(changed_identities)
                    and not has_unobserved_inflow
                )
            )
            if not should_emit:
                previous_assets = current_assets
                previous_asset_values = current_values
                continue

            bucket_values = self._sum_by_type(current_values)
            bucket_costs = self._sum_by_type(current_costs)
            bucket_flows = self._sum_by_type(pending_period_flows)
            bucket_contributions = self._sum_by_type(contributions)
            product_types = (
                set(bucket_values)
                | set(bucket_costs)
                | set(bucket_flows)
                | set(bucket_contributions)
                | set(previous_values)
            )
            breakdown: dict[str, GainsMetrics] = {}
            for product_type in sorted(product_types, key=lambda item: item.value):
                value = bucket_values.get(product_type, Dezimal(0))
                previous = previous_values[product_type]
                period_flow = bucket_flows.get(product_type, Dezimal(0))
                period_return = self._period_return(value, period_flow, previous)
                indices[product_type] = indices[product_type] * (1 + period_return)
                net_flows = bucket_contributions.get(product_type, Dezimal(0))
                if bounded:
                    gain = (
                        value
                        - opening_by_type.get(product_type, Dezimal(0))
                        - net_flows
                    )
                else:
                    gain = value - net_flows
                breakdown[product_type.value] = GainsMetrics(
                    value=value,
                    cost_basis=bucket_costs.get(product_type, Dezimal(0)),
                    net_contributions=net_flows,
                    gain=gain,
                    period_return=period_return,
                    index=indices[product_type],
                )
                previous_values[product_type] = value

            total_value = sum(bucket_values.values(), Dezimal(0))
            total_cost = sum(bucket_costs.values(), Dezimal(0))
            total_flow = sum(bucket_flows.values(), Dezimal(0))
            total_contributions = sum(bucket_contributions.values(), Dezimal(0))
            total_return = self._period_return(total_value, total_flow, previous_total)
            total_index = total_index * (1 + total_return)
            total_gain = (
                total_value - opening_total - total_contributions
                if bounded
                else total_value - total_contributions
            )
            points.append(
                GainsTimelinePoint(
                    date=day,
                    metrics=GainsMetrics(
                        value=total_value,
                        cost_basis=total_cost,
                        net_contributions=total_contributions,
                        gain=total_gain,
                        period_return=total_return,
                        index=total_index,
                    ),
                    breakdown=breakdown,
                )
            )
            previous_total = total_value
            previous_assets = current_assets
            previous_asset_values = current_values
            pending_period_flows.clear()

        quality, warnings = self._hybrid_quality(provenance)
        if orphan_sell_flow_ids:
            warnings.append(
                "Some sell transactions had no matching buy and were excluded "
                "from gains; the position history is incomplete."
            )
        xirr: Optional[Dezimal] = None
        annualized_xirr: Optional[Dezimal] = None
        not_applicable_reasons: list[str] = []
        if len(points) >= 2:
            if GainsFlowProvenance.UNKNOWN in provenance:
                not_applicable_reasons.append(
                    "IRR unavailable because an external flow amount or asset "
                    "movement could not be valued."
                )
            else:
                xirr = self._xirr(points, daily_net_flows)
                annualized_xirr = self._annualized_xirr(xirr, points)
        return GainsTimeline(
            currency=query.base_currency,
            points=points,
            quality=quality,
            xirr=xirr,
            annualized_xirr=annualized_xirr,
            opening_value=opening_total if bounded else None,
            warnings=warnings,
            not_applicable_reasons=not_applicable_reasons,
        )

    @staticmethod
    def _annualized_xirr(
        xirr: Optional[Dezimal], points: list[GainsTimelinePoint]
    ) -> Optional[Dezimal]:
        if xirr is None:
            return None
        days = (points[-1].date - points[0].date).days
        if days < 30:
            return None
        years = days / 365.25
        factor = (1.0 + float(xirr)) ** years
        if not math.isfinite(factor):
            return None
        return Dezimal(str(round(factor - 1.0, 10)))

    @staticmethod
    def _xirr(
        points: list[GainsTimelinePoint],
        daily_net_flows: list[tuple[date, Dezimal]],
    ) -> Optional[Dezimal]:
        start = points[0]
        end = points[-1]
        cash_flows: list[tuple[date, float]] = []
        start_value = float(start.metrics.value)
        if start_value > 0:
            cash_flows.append((start.date, -start_value))
        for day, flow in daily_net_flows:
            amount = float(flow)
            if amount != 0 and day > start.date:
                cash_flows.append((day, -amount))
        end_value = float(end.metrics.value)
        if end_value > 0:
            cash_flows.append((end.date, end_value))
        if len(cash_flows) < 2:
            return None
        has_positive = any(amount > 0 for _, amount in cash_flows)
        has_negative = any(amount < 0 for _, amount in cash_flows)
        if not has_positive or not has_negative:
            return None

        origin = cash_flows[0][0]

        def npv(rate: float) -> Optional[float]:
            if rate <= -0.999999999:
                return None
            base = 1.0 + rate
            total = 0.0
            for day, amount in cash_flows:
                years = (day - origin).days / 365.25
                total += amount / base**years
            return total if math.isfinite(total) else None

        low = -0.999999
        high = 10.0
        npv_low = npv(low)
        if npv_low is None:
            return None
        npv_high = npv(high)
        expanded = 0
        while npv_high is not None and npv_low * npv_high > 0 and expanded < 16:
            high *= 2.0
            npv_high = npv(high)
            expanded += 1
        if npv_high is None or npv_low * npv_high > 0:
            return None

        for _ in range(128):
            mid = (low + high) / 2.0
            npv_mid = npv(mid)
            if npv_mid is None:
                return None
            if abs(npv_mid) < 1e-7 or abs(high - low) < 1e-10:
                return Dezimal(str(round(mid, 10)))
            if npv_low * npv_mid > 0:
                low = mid
                npv_low = npv_mid
            else:
                high = mid
        return None

    @staticmethod
    def _hybrid_quality(
        provenance: set[GainsFlowProvenance],
    ) -> tuple[GainsQuality, list[str]]:
        if GainsFlowProvenance.UNKNOWN in provenance:
            return GainsQuality.DEGRADED, [
                "Some flows could not be valued or reconciled; results may be "
                "incomplete."
            ]
        warnings: list[str] = []
        if GainsFlowProvenance.REPLAYED_POSITIONS in provenance:
            warnings.append(
                "Some positions were reconstructed from transactions without "
                "stored market values; valuations before the first stored "
                "position use transaction cost."
            )
        if provenance & {
            GainsFlowProvenance.QUANTITY_RESIDUAL,
            GainsFlowProvenance.NET_CONTRIBUTION_FALLBACK,
        }:
            warnings.append(
                "Some flows were inferred from quantity or cost-basis changes; "
                "contributions and returns may be estimates."
            )
        if warnings:
            return GainsQuality.ESTIMATED, warnings
        return GainsQuality.COMPLETE, []

    def _calculate_snapshots(
        self,
        query: GainsTimelineQuery,
        snapshots: list[AssetSnapshot],
        rates,
        historic: _HistoricRates,
        yesterday: date,
    ) -> GainsTimeline:
        snapshots = [
            snapshot for snapshot in snapshots if snapshot.moment.date() <= yesterday
        ]
        if not snapshots:
            return self._empty(query)

        snapshots_by_day: dict[date, list[AssetSnapshot]] = defaultdict(list)
        for snapshot in snapshots:
            snapshots_by_day[snapshot.moment.date()].append(snapshot)
        days = set(snapshots_by_day)
        days.update(self._commodity_days(snapshots, query.assets, historic, yesterday))
        if days:
            day = min(days)
            day_end = max(days)
            while day <= day_end:
                days.add(day)
                day += timedelta(days=1)
        output_days = sorted(days)
        if not output_days:
            return self._empty(query)

        current: dict[str, dict[_AssetIdentity, AssetValuation]] = {}
        deleted_at: dict[str, date] = {}
        points: list[GainsTimelinePoint] = []
        last_known_basis = False
        last_missing_basis = False
        last_has_value = False

        for day in output_days:
            for snapshot in sorted(
                snapshots_by_day.get(day, []), key=lambda snapshot: snapshot.moment
            ):
                holder_assets: dict[_AssetIdentity, AssetValuation] = {}
                for valuation in snapshot.valuations:
                    if not self._matches(
                        valuation.product_type,
                        valuation.asset_key,
                        query.assets,
                        valuation.portfolio_name,
                        valuation.equity_type,
                        valuation.wallet_id,
                    ):
                        continue
                    identity = self._valuation_identity(snapshot.holder, valuation)
                    holder_assets[identity] = valuation
                current[snapshot.holder] = holder_assets
                if snapshot.holder_deleted_at is not None:
                    deleted_at[snapshot.holder] = snapshot.holder_deleted_at

            for holder, holder_deleted_at in deleted_at.items():
                if day >= holder_deleted_at and current.get(holder):
                    current[holder] = {}

            current_assets = self._flatten(current)
            current_values: dict[_AssetIdentity, Dezimal] = {}
            for identity, valuation in current_assets.items():
                value = self._valuation_value(
                    identity,
                    valuation,
                    day,
                    query.accrue_fixed_income,
                    query.base_currency,
                    rates,
                    {},
                    {},
                    historic,
                )
                if value is not None:
                    current_values[identity] = value

            current_costs: dict[_AssetIdentity, Dezimal] = {}
            covered_values: dict[_AssetIdentity, Dezimal] = {}
            covered_costs: dict[_AssetIdentity, Dezimal] = {}
            day_known_basis = False
            day_missing_basis = False
            for identity, value in current_values.items():
                valuation = current_assets[identity]
                cost = (
                    self._convert(
                        valuation.cost_basis,
                        valuation.currency,
                        query.base_currency,
                        rates,
                    )
                    if valuation.cost_basis is not None
                    else None
                )
                if cost is None:
                    day_missing_basis = True
                    continue
                day_known_basis = True
                current_costs[identity] = cost
                covered_values[identity] = value
                covered_costs[identity] = cost

            last_known_basis = day_known_basis
            last_missing_basis = day_missing_basis
            last_has_value = bool(current_values)

            bucket_values = self._sum_by_type(current_values)
            bucket_costs = self._sum_by_type(current_costs)
            bucket_covered_values = self._sum_by_type(covered_values)
            bucket_covered_costs = self._sum_by_type(covered_costs)
            product_types = set(bucket_values) | set(bucket_costs)
            breakdown: dict[str, GainsMetrics] = {}
            for product_type in sorted(product_types, key=lambda item: item.value):
                breakdown[product_type.value] = self._snapshot_metrics(
                    bucket_values.get(product_type, Dezimal(0)),
                    bucket_costs.get(product_type, Dezimal(0)),
                    bucket_covered_values.get(product_type),
                    bucket_covered_costs.get(product_type),
                )

            total_value = sum(bucket_values.values(), Dezimal(0))
            total_cost = sum(bucket_costs.values(), Dezimal(0))
            points.append(
                GainsTimelinePoint(
                    date=day,
                    metrics=self._snapshot_metrics(
                        total_value,
                        total_cost,
                        (
                            sum(bucket_covered_values.values(), Dezimal(0))
                            if day_known_basis
                            else None
                        ),
                        (
                            sum(bucket_covered_costs.values(), Dezimal(0))
                            if day_known_basis
                            else None
                        ),
                    ),
                    breakdown=breakdown,
                )
            )

        if not last_has_value:
            basis_status = GainsBasisStatus.NOT_APPLICABLE
        elif not last_known_basis:
            basis_status = GainsBasisStatus.UNKNOWN
        elif last_missing_basis:
            basis_status = GainsBasisStatus.PARTIAL_UNKNOWN
        else:
            basis_status = GainsBasisStatus.COMPLETE

        warnings: list[str] = []
        not_applicable_reasons: list[str] = []
        if basis_status == GainsBasisStatus.PARTIAL_UNKNOWN:
            warnings.append(
                "Some positions have no recorded cost basis; gain covers only "
                "positions with a known basis."
            )
        elif basis_status == GainsBasisStatus.UNKNOWN:
            not_applicable_reasons.append(
                "Gain versus cost basis unavailable: no cost basis recorded for "
                "the selected positions."
            )

        return GainsTimeline(
            currency=query.base_currency,
            points=points,
            method=GainsMethod.SNAPSHOT_BOOK_BASIS,
            basis=GainsBasis.BOOK_BASIS,
            quality=(
                GainsQuality.COMPLETE
                if basis_status == GainsBasisStatus.COMPLETE
                else GainsQuality.DEGRADED
            ),
            basis_status=basis_status,
            warnings=warnings,
            not_applicable_reasons=not_applicable_reasons,
        )

    @staticmethod
    def _snapshot_metrics(
        value: Dezimal,
        cost_basis: Dezimal,
        covered_value: Optional[Dezimal],
        covered_cost: Optional[Dezimal],
    ) -> GainsMetrics:
        gain = (
            covered_value - covered_cost
            if covered_value is not None and covered_cost is not None
            else None
        )
        return GainsMetrics(
            value=value,
            cost_basis=cost_basis,
            net_contributions=cost_basis,
            gain=gain,
            period_return=None,
            index=None,
        )

    def _fixed_income_days(
        self,
        snapshots: list[AssetSnapshot],
        assets: list[GainsAssetFilter],
        upper: date,
    ) -> set[date]:
        by_holder: dict[str, list[AssetSnapshot]] = defaultdict(list)
        for snapshot in snapshots:
            by_holder[snapshot.holder].append(snapshot)

        days: set[date] = set()
        for holder_snapshots in by_holder.values():
            holder_snapshots.sort(key=lambda snapshot: snapshot.moment)
            for index, snapshot in enumerate(holder_snapshots):
                if not any(
                    valuation.product_type in _FIXED_INCOME_TYPES
                    and self._matches(
                        valuation.product_type,
                        valuation.asset_key,
                        assets,
                        valuation.portfolio_name,
                        valuation.equity_type,
                        valuation.wallet_id,
                    )
                    for valuation in snapshot.valuations
                ):
                    continue
                start = snapshot.moment.date()
                next_snapshot = (
                    holder_snapshots[index + 1].moment.date()
                    if index + 1 < len(holder_snapshots)
                    else upper + timedelta(days=1)
                )
                end = min(upper, next_snapshot - timedelta(days=1))
                if snapshot.holder_deleted_at is not None:
                    end = min(end, snapshot.holder_deleted_at - timedelta(days=1))
                while start <= end:
                    days.add(start)
                    start += timedelta(days=1)
        return days

    def _commodity_days(
        self,
        snapshots: list[AssetSnapshot],
        assets: list[GainsAssetFilter],
        historic: _HistoricRates,
        yesterday: date,
    ) -> set[date]:
        first_days: dict[CommodityType, date] = {}
        for snapshot in snapshots:
            snapshot_day = snapshot.moment.date()
            if snapshot_day >= COMMODITY_HISTORIC_CUTOFF:
                continue
            for valuation in snapshot.valuations:
                if (
                    not self._is_historically_revaluable(valuation)
                    or not self._matches(
                        valuation.product_type,
                        valuation.asset_key,
                        assets,
                        valuation.portfolio_name,
                        valuation.equity_type,
                        valuation.wallet_id,
                    )
                    or historic.get(valuation.commodity_type) is None
                ):
                    continue
                current_first = first_days.get(valuation.commodity_type)
                if current_first is None or snapshot_day < current_first:
                    first_days[valuation.commodity_type] = snapshot_day

        upper = min(yesterday, COMMODITY_HISTORIC_CUTOFF - timedelta(days=1))
        return {
            day
            for commodity_type, first_day in first_days.items()
            for day in historic[commodity_type].days
            if first_day <= day <= upper
        }

    @staticmethod
    def _is_historically_revaluable(valuation: AssetValuation) -> bool:
        return (
            valuation.product_type == ProductType.COMMODITY
            and valuation.commodity_type is not None
            and valuation.weight is not None
            and valuation.weight_unit is not None
        )

    def _inferred_flow(
        self,
        identity: _AssetIdentity,
        previous: Optional[AssetValuation],
        current: Optional[AssetValuation],
        previous_values_by_asset: dict[_AssetIdentity, Dezimal],
        prior_values_by_asset: dict[_AssetIdentity, Dezimal],
        flows: list[GainsFlow],
        has_settlement: bool,
        target_currency: str,
        rates,
    ) -> tuple[Optional[Dezimal], Optional[GainsFlowProvenance]]:
        if previous is None and current is None:
            return None, None

        previous_value = prior_values_by_asset.get(identity, Dezimal(0))
        current_value = previous_values_by_asset.get(identity, Dezimal(0))
        has_transaction_cash = any(
            self._transaction_cash(flow) not in (None, Dezimal(0)) for flow in flows
        )

        if current is None:
            if has_transaction_cash or has_settlement:
                return None, None
            return -previous_value, GainsFlowProvenance.UNKNOWN

        if previous is None:
            return self._opening_flow(
                current,
                current_value,
                flows,
                target_currency,
                rates,
            )

        if previous.quantity is not None and current.quantity is not None:
            transaction_quantity = Dezimal(0)
            has_unquantified_trade = False
            for flow in flows:
                if flow.transaction_type not in _POSITION_CHANGING_TYPES:
                    continue
                if flow.quantity is None:
                    has_unquantified_trade = True
                    continue
                if flow.transaction_type in _INFLOW_TYPES:
                    transaction_quantity += flow.quantity
                else:
                    transaction_quantity -= flow.quantity
            if has_unquantified_trade:
                return None, None
            residual_quantity = (
                current.quantity - previous.quantity - transaction_quantity
            )
            if residual_quantity == 0:
                return None, None
            unit_value = self._unit_value(
                current.quantity,
                current_value,
                previous.quantity,
                previous_value,
            )
            if unit_value is None:
                return None, None
            return residual_quantity * unit_value, GainsFlowProvenance.QUANTITY_RESIDUAL

        if has_transaction_cash:
            return None, None
        if previous.cost_basis is not None and current.cost_basis is not None:
            previous_cost = self._convert(
                previous.cost_basis, previous.currency, target_currency, rates
            )
            current_cost = self._convert(
                current.cost_basis, current.currency, target_currency, rates
            )
            if previous_cost is not None and current_cost is not None:
                return (
                    current_cost - previous_cost,
                    GainsFlowProvenance.NET_CONTRIBUTION_FALLBACK,
                )
        return None, None

    def _replay_windows(
        self,
        flows: list[GainsFlow],
        snapshots: list[AssetSnapshot],
        query: GainsTimelineQuery,
        yesterday: date,
        range_from: Optional[date] = None,
    ) -> tuple[dict[_AssetIdentity, tuple[date, date, date]], set[date]]:
        latest_pre_range: dict[tuple[str, ProductType, str, str, str], date] = {}
        covering_snapshot_day: dict[tuple[str, ProductType, str, str, str], date] = {}
        covering_identity: dict[
            tuple[str, ProductType, str, str, str], _AssetIdentity
        ] = {}
        for snapshot in snapshots:
            snapshot_day = snapshot.moment.date()
            for valuation in snapshot.valuations:
                if not self._matches(
                    valuation.product_type,
                    valuation.asset_key,
                    query.assets,
                    valuation.portfolio_name,
                    valuation.equity_type,
                    valuation.wallet_id,
                ):
                    continue
                identity = GetGainsTimelineImpl._valuation_identity(
                    snapshot.holder, valuation
                )
                key = GetGainsTimelineImpl._identity_key(identity)
                if range_from is not None and snapshot_day < range_from:
                    if snapshot_day > latest_pre_range.get(key, date.min):
                        latest_pre_range[key] = snapshot_day
                elif snapshot_day < covering_snapshot_day.get(key, date.max):
                    covering_snapshot_day[key] = snapshot_day
                    covering_identity[key] = identity

        bounds: dict[_AssetIdentity, list[date]] = {}
        flow_days: dict[_AssetIdentity, set[date]] = defaultdict(set)
        for flow in flows:
            if (
                flow.product_type not in _REPLAY_PRODUCT_TYPES
                or flow.transaction_type not in _POSITION_CHANGING_TYPES
                or not self._matches(
                    flow.product_type,
                    flow.asset_key,
                    query.assets,
                    flow.portfolio_name,
                    flow.equity_type,
                    flow.wallet_id,
                )
            ):
                continue
            identity = GetGainsTimelineImpl._flow_identity(flow)
            flow_day = flow.moment.date()
            entry = bounds.setdefault(identity, [flow_day, flow_day])
            entry[0] = min(entry[0], flow_day)
            entry[1] = max(entry[1], flow_day)
            flow_days[identity].add(flow_day)

        windows: dict[_AssetIdentity, tuple[date, date]] = {}
        days: set[date] = set()
        for identity, (first_day, last_day) in bounds.items():
            key = GetGainsTimelineImpl._identity_key(identity)
            replay_from = latest_pre_range.get(key)
            eligible = [
                day
                for day in flow_days[identity]
                if replay_from is None or day > replay_from
            ]
            if not eligible:
                continue
            first = min(eligible)
            last = max(eligible)
            covering = covering_snapshot_day.get(key)
            if covering is not None and covering <= first:
                continue
            end = min(last, covering - timedelta(days=1)) if covering else last
            if first > end:
                continue
            if (
                range_from is not None
                and last < range_from
                and self._net_quantity_is_zero(
                    flow for flow in flows if self._flow_identity(flow) == identity
                )
            ):
                continue
            window_identity = covering_identity.get(key, identity)
            tail_end = (covering - timedelta(days=1)) if covering else yesterday
            windows[window_identity] = (first, end, tail_end)
            days.update(day for day in eligible if first <= day <= end)
            day = first
            while day <= tail_end:
                days.add(day)
                day += timedelta(days=1)
        return windows, days

    def _split_adjusted_quantity(self, flow: GainsFlow) -> Optional[Dezimal]:
        if flow.quantity is None:
            return None
        splits = self._splits_by_key.get(flow.asset_key)
        if not splits:
            return flow.quantity
        ratio = Dezimal(1)
        flow_day = flow.moment.date()
        for split_day, split_ratio in splits.items():
            if flow_day < split_day:
                ratio *= split_ratio
        return flow.quantity * ratio

    def _update_replay_position(
        self,
        positions: dict[_AssetIdentity, _ReplayPosition],
        flow: GainsFlow,
        identity: Optional[_AssetIdentity] = None,
        orphan_sell_flow_ids: Optional[set[int]] = None,
    ) -> None:
        if flow.transaction_type not in _POSITION_CHANGING_TYPES:
            return
        if identity is None:
            identity = self._flow_identity(flow)
        position = positions.setdefault(identity, _ReplayPosition())
        quantity = self._split_adjusted_quantity(flow)
        if flow.transaction_type in _INFLOW_TYPES:
            cash = self._transaction_cash(flow)
            position.book_value += cash if cash is not None else flow.amount
            if position.quantity is not None and quantity is not None:
                position.quantity += quantity
            else:
                position.quantity = None
            return
        if (
            position.quantity is not None
            and quantity is not None
            and position.quantity > 0
        ):
            ratio = min(quantity / position.quantity, Dezimal(1))
            position.book_value -= position.book_value * ratio
            position.quantity -= quantity
            if position.quantity <= 0:
                position.quantity = Dezimal(0)
                position.book_value = Dezimal(0)
        else:
            if (
                orphan_sell_flow_ids is not None
                and flow.transaction_type in _OUTFLOW_TYPES
                and quantity
            ):
                orphan_sell_flow_ids.add(id(flow))
            position.quantity = Dezimal(0)
            position.book_value = Dezimal(0)

    async def _load_replay_history(
        self,
        query: GainsTimelineQuery,
        snapshots: list[AssetSnapshot],
        flows: list[GainsFlow],
        yesterday: date,
        range_from: Optional[date],
    ) -> dict[str, dict[date, Dezimal]]:
        if self._instrument_history_provider is None:
            return {}
        replay_windows, _ = self._replay_windows(
            flows, snapshots, query, yesterday, range_from
        )
        if not replay_windows:
            return {}

        requests: dict[str, InstrumentDataRequest] = {}
        windows_by_key: dict[str, tuple[date, date]] = {}
        names_by_key: dict[str, str] = {}
        currencies_by_key: dict[str, str] = {}
        etf_keys: set[str] = set()
        for snapshot in snapshots:
            for valuation in snapshot.valuations:
                if valuation.equity_type == EquityType.ETF:
                    etf_keys.add(valuation.asset_key)
        for flow in flows:
            if flow.name and flow.asset_key not in names_by_key:
                names_by_key[flow.asset_key] = flow.name
            if flow.currency and flow.asset_key not in currencies_by_key:
                currencies_by_key[flow.asset_key] = flow.currency
            if flow.equity_type == EquityType.ETF:
                etf_keys.add(flow.asset_key)
        for identity, (first_day, last_day, _tail_end) in replay_windows.items():
            product_type, asset_key = identity[1], identity[2]
            if product_type == ProductType.FUND:
                instrument_type = InstrumentType.MUTUAL_FUND
            elif product_type == ProductType.STOCK_ETF:
                instrument_type = (
                    InstrumentType.ETF
                    if asset_key in etf_keys
                    else InstrumentType.STOCK
                )
            else:
                continue
            if asset_key not in requests:
                requests[asset_key] = self._history_request(
                    asset_key,
                    instrument_type,
                    names_by_key.get(asset_key),
                    currencies_by_key.get(asset_key),
                )
            current = windows_by_key.get(asset_key)
            if current is None:
                windows_by_key[asset_key] = (first_day, last_day)
            else:
                windows_by_key[asset_key] = (
                    min(current[0], first_day),
                    max(current[1], last_day),
                )
        if not requests:
            return {}

        history_points: dict[str, list] = {}
        for key, request in requests.items():
            window_start, window_end = windows_by_key[key]
            if self._instrument_price_history is None:
                stored = []
                covered = None
                no_result = False
            else:
                stored = await self._instrument_price_history.get_history(
                    key, window_start, window_end
                )
                covered = await self._instrument_price_history.get_covered_range(key)
                no_result = await self._instrument_price_history.is_no_result(key)
            if no_result and not stored:
                continue
            preferred_symbol = None
            preferred_source = None
            if self._instrument_price_history is not None:
                resolved = await self._instrument_price_history.get_resolved_symbol(key)
                if resolved:
                    preferred_symbol, preferred_source = resolved

            gaps: list[tuple[date, date]] = []
            if covered is None:
                gaps.append((window_start, window_end))
            else:
                covered_start, covered_end = covered
                if covered_start > window_start:
                    gaps.append((window_start, covered_start - timedelta(days=1)))
                if covered_end < window_end:
                    gaps.append((covered_end + timedelta(days=1), window_end))

            merged = list(stored)
            for gap_start, gap_end in gaps:
                if gap_start > gap_end:
                    continue
                if not self._has_weekday(gap_start, gap_end):
                    continue
                if self._instrument_price_history is not None:
                    known_empty = (
                        await self._instrument_price_history.get_empty_gap_days(
                            key, gap_start, gap_end
                        )
                    )
                else:
                    known_empty = set()
                fetch_start = gap_start
                while fetch_start in known_empty and fetch_start <= gap_end:
                    fetch_start += timedelta(days=1)
                fetch_end = gap_end
                while fetch_end in known_empty and fetch_end >= fetch_start:
                    fetch_end -= timedelta(days=1)
                if fetch_start > fetch_end:
                    continue
                if not self._has_weekday(fetch_start, fetch_end):
                    if self._instrument_price_history is not None:
                        await self._instrument_price_history.mark_empty_gap_days(
                            key,
                            [
                                day
                                for day in self._days_between(fetch_start, fetch_end)
                                if day not in known_empty
                            ],
                        )
                    continue
                (
                    fetched,
                    symbol,
                    source,
                ) = await self._instrument_history_provider.get_history(
                    request,
                    fetch_start,
                    fetch_end + timedelta(days=1),
                    preferred_symbol,
                    preferred_source,
                )
                if not fetched:
                    if self._instrument_price_history is not None:
                        empty_days = [
                            day
                            for day in self._days_between(fetch_start, fetch_end)
                            if day not in known_empty
                        ]
                        await self._instrument_price_history.mark_empty_gap_days(
                            key, empty_days
                        )
                    continue
                if self._instrument_price_history is not None:
                    await self._instrument_price_history.upsert(
                        key, fetched, source=source or "unknown"
                    )
                    if symbol:
                        await self._instrument_price_history.save_resolved_symbol(
                            key, symbol, source=source or "unknown"
                        )
                        preferred_symbol = symbol
                        preferred_source = source
                    last_point = max(point.date for point in fetched)
                    settled_before = yesterday - timedelta(days=_TAIL_SETTLE_DAYS)
                    if last_point < fetch_end and fetch_end <= settled_before:
                        await self._instrument_price_history.mark_empty_gap_days(
                            key,
                            [
                                day
                                for day in self._days_between(
                                    last_point + timedelta(days=1), fetch_end
                                )
                                if day not in known_empty
                            ],
                        )
                merged.extend(fetched)
            if merged:
                history_points[key] = sorted(
                    {point.date: point for point in merged}.values(),
                    key=lambda point: point.date,
                )
            elif not stored and self._instrument_price_history is not None:
                await self._instrument_price_history.mark_no_result(key)
        if history_points:
            self._splits_by_key.update(
                await self._load_splits(requests, windows_by_key)
            )
        return {
            key: {point.date: point.price for point in points}
            for key, points in history_points.items()
        }

    @staticmethod
    def _net_quantity_is_zero(flows) -> bool:
        quantity = Dezimal(0)
        has_quantified = False
        for flow in flows:
            if flow.transaction_type not in _POSITION_CHANGING_TYPES:
                continue
            if flow.quantity is None:
                return False
            has_quantified = True
            if flow.transaction_type in _INFLOW_TYPES:
                quantity += flow.quantity
            else:
                quantity -= flow.quantity
        return has_quantified and quantity <= 0

    @staticmethod
    def _has_weekday(from_date: date, to_date: date) -> bool:
        span = (to_date - from_date).days + 1
        if span > 7:
            return True
        day = from_date
        while day <= to_date:
            if day.weekday() < 5:
                return True
            day += timedelta(days=1)
        return False

    @staticmethod
    def _days_between(from_date: date, to_date: date) -> list[date]:
        days = []
        day = from_date
        while day <= to_date:
            days.append(day)
            day += timedelta(days=1)
        return days

    async def _load_splits(
        self,
        requests: dict[str, InstrumentDataRequest],
        windows_by_key: dict[str, tuple[date, date]],
    ) -> dict[str, dict[date, Dezimal]]:
        if self._instrument_history_provider is None:
            return {}
        get_splits = getattr(self._instrument_history_provider, "get_splits", None)
        if get_splits is None:
            return {}
        result: dict[str, dict[date, Dezimal]] = {}
        today = datetime.now(tzlocal()).date()
        storage = self._instrument_price_history
        for key, request in requests.items():
            if request.type == InstrumentType.MUTUAL_FUND:
                continue
            window_start, _ = windows_by_key[key]
            if storage is not None:
                if await storage.is_no_result(key):
                    continue
                if await storage.is_splits_checked(key):
                    cached = await storage.get_splits(key)
                    if cached:
                        result[key] = {split.date: split.ratio for split in cached}
                    continue
            preferred_symbol = None
            preferred_source = None
            if storage is not None:
                resolved = await storage.get_resolved_symbol(key)
                if resolved:
                    preferred_symbol, preferred_source = resolved
            splits = await get_splits(
                request, window_start, today, preferred_symbol, preferred_source
            )
            if splits is None:
                continue
            if storage is not None:
                if splits:
                    await storage.save_splits(key, splits)
                await storage.mark_splits_checked(key)
            if splits:
                result[key] = {split.date: split.ratio for split in splits}
        return result

    @staticmethod
    def _history_request(
        asset_key: str,
        instrument_type: InstrumentType,
        name: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> InstrumentDataRequest:
        looks_like_isin = (
            len(asset_key) == 12
            and asset_key[:2].isalpha()
            and asset_key[:2].isupper()
            and asset_key[2:].isalnum()
        )
        if looks_like_isin:
            return InstrumentDataRequest(
                type=instrument_type, isin=asset_key, name=name, currency=currency
            )
        return InstrumentDataRequest(
            type=instrument_type, ticker=asset_key, name=name, currency=currency
        )

    def _replay_valuation(
        self,
        identity: _AssetIdentity,
        position: _ReplayPosition,
        day: Optional[date] = None,
        history_by_key: Optional[dict[str, dict[date, Dezimal]]] = None,
        rates=None,
        target_currency: Optional[str] = None,
    ) -> AssetValuation:
        (
            _,
            product_type,
            asset_key,
            currency,
            portfolio_name,
            equity_type,
            wallet_id,
        ) = identity
        market_value = position.book_value
        if (
            day is not None
            and history_by_key
            and position.quantity is not None
            and position.quantity > 0
        ):
            prices = history_by_key.get(asset_key)
            if prices:
                price = self._price_at(prices, day)
                if price is not None:
                    market_value = position.quantity * price
        return AssetValuation(
            product_type=product_type,
            asset_key=asset_key,
            currency=currency,
            market_value=market_value,
            quantity=position.quantity,
            cost_basis=position.book_value,
            portfolio_name=portfolio_name or None,
            equity_type=EquityType(equity_type) if equity_type else None,
            wallet_id=UUID(wallet_id) if wallet_id else None,
        )

    @staticmethod
    def _price_at(prices: dict[date, Dezimal], day: date) -> Optional[Dezimal]:
        price = prices.get(day)
        if price is not None:
            return price
        earlier = [d for d in prices if d < day]
        if not earlier:
            return None
        return prices[max(earlier)]

    @staticmethod
    def _retain_fixed_income_terms(
        previous: Optional[AssetValuation],
        current: AssetValuation,
    ) -> AssetValuation:
        if (
            previous is None
            or current.product_type not in _FIXED_INCOME_TYPES
            or previous.product_type != current.product_type
        ):
            return current
        interest_rate = current.interest_rate
        extended_interest_rate = current.extended_interest_rate
        if interest_rate in (None, Dezimal(0)) and previous.interest_rate not in (
            None,
            Dezimal(0),
        ):
            interest_rate = previous.interest_rate
        if extended_interest_rate in (None, Dezimal(0)) and (
            previous.extended_interest_rate not in (None, Dezimal(0))
        ):
            extended_interest_rate = previous.extended_interest_rate
        if (
            interest_rate == current.interest_rate
            and extended_interest_rate == current.extended_interest_rate
        ):
            return current
        return replace(
            current,
            interest_rate=interest_rate,
            extended_interest_rate=extended_interest_rate,
        )

    @staticmethod
    def _valuation_identity(holder: str, valuation: AssetValuation) -> _AssetIdentity:
        return (
            holder,
            valuation.product_type,
            valuation.asset_key,
            valuation.currency,
            valuation.portfolio_name or "",
            valuation.equity_type.value if valuation.equity_type else "",
            str(valuation.wallet_id) if valuation.wallet_id else "",
        )

    @staticmethod
    def _flow_identity(flow: GainsFlow) -> _AssetIdentity:
        return (
            flow.holder,
            flow.product_type,
            flow.asset_key,
            flow.currency,
            flow.portfolio_name or "",
            flow.equity_type.value if flow.equity_type else "",
            str(flow.wallet_id) if flow.wallet_id else "",
        )

    @staticmethod
    def _identity_key(
        identity: _AssetIdentity,
    ) -> tuple[str, ProductType, str, str, str]:
        holder, product_type, asset_key, currency, _, _, wallet_id = identity
        return holder, product_type, asset_key, currency, wallet_id

    @staticmethod
    def _requires_market_position_observation(flow: GainsFlow) -> bool:
        return (
            flow.product_type not in _FIXED_INCOME_TYPES
            and flow.transaction_type in _POSITION_CHANGING_TYPES
            and flow.transaction_type not in _TRANSFER_OUT_TYPES
            and flow.transaction_type not in _TRANSFER_IN_TYPES
            and flow.quantity is not None
        )

    @staticmethod
    def _market_position_change_is_observed(
        previous: Optional[AssetValuation], current: Optional[AssetValuation]
    ) -> bool:
        if previous is None or current is None:
            return True
        if previous.quantity is None or current.quantity is None:
            return True
        return previous.quantity != current.quantity

    def _record_observed_market_flows(
        self,
        pending_market_flows: dict[_AssetIdentity, list[GainsFlow]],
        changed_identities: set[_AssetIdentity],
        previous_assets: dict[_AssetIdentity, AssetValuation],
        current_assets: dict[_AssetIdentity, AssetValuation],
        period_flows: dict[_AssetIdentity, Dezimal],
        contributions: dict[_AssetIdentity, Dezimal],
        unreconciled_flows: dict[_AssetIdentity, list[GainsFlow]],
        target_currency: str,
        rates,
        accrual_mode: FixedIncomeAccrual,
        provenance: set[GainsFlowProvenance],
        replay_keys: Optional[set[tuple[str, ProductType, str, str, str]]] = None,
    ):
        replay_keys = replay_keys or set()
        for identity in changed_identities:
            if self._identity_key(identity) in replay_keys:
                continue
            flows = pending_market_flows.get(identity)
            if not flows or not self._market_position_change_is_observed(
                previous_assets.get(identity), current_assets.get(identity)
            ):
                continue
            for flow in flows:
                self._record_flow(
                    flow,
                    identity,
                    period_flows,
                    contributions,
                    unreconciled_flows,
                    target_currency,
                    rates,
                    accrual_mode,
                    provenance,
                )
            del pending_market_flows[identity]

    @staticmethod
    def _is_full_transfer_exit(
        flow: GainsFlow, previous: Optional[AssetValuation]
    ) -> bool:
        return (
            flow.transaction_type in _TRANSFER_OUT_TYPES
            and flow.quantity is not None
            and previous is not None
            and previous.quantity is not None
            and flow.quantity >= previous.quantity
        )

    @staticmethod
    def _pop_matching_transfer_out(
        pending_transfer_outs: list[GainsFlow], incoming: GainsFlow
    ) -> Optional[GainsFlow]:
        is_switch = incoming.transaction_type in {TxType.SWITCH_TO}
        tolerance = Dezimal("0.02")
        max_days = 1 if is_switch else 7
        incoming_day = incoming.moment.date()
        for index, outgoing in enumerate(pending_transfer_outs):
            if (
                outgoing.holder != incoming.holder
                or outgoing.product_type != incoming.product_type
                or outgoing.currency != incoming.currency
                or outgoing.asset_key == incoming.asset_key
                or outgoing.wallet_id != incoming.wallet_id
            ):
                continue
            day_gap = abs((incoming_day - outgoing.moment.date()).days)
            if day_gap > max_days:
                continue
            amount_delta = abs(outgoing.amount - incoming.amount)
            reference = max(abs(outgoing.amount), abs(incoming.amount), Dezimal(1))
            if amount_delta / reference > tolerance:
                continue
            return pending_transfer_outs.pop(index)
        return None

    @classmethod
    def _internal_transfer_flow_ids(cls, flows: list[GainsFlow]) -> set[int]:
        pending_transfer_outs: list[GainsFlow] = []
        matched_ids: set[int] = set()
        for flow in flows:
            if flow.transaction_type in _TRANSFER_OUT_TYPES:
                pending_transfer_outs.append(flow)
                continue
            if flow.transaction_type not in _TRANSFER_IN_TYPES:
                continue
            outgoing = cls._pop_matching_transfer_out(pending_transfer_outs, flow)
            if outgoing is not None:
                matched_ids.add(id(outgoing))
                matched_ids.add(id(flow))
        return matched_ids

    def _detect_fund_transfers(
        self,
        snapshots: list[AssetSnapshot],
        flows: list[GainsFlow],
    ) -> tuple[
        dict[tuple[str, ProductType, str, str, str], Dezimal],
        set[tuple[str, ProductType, str, str, str]],
    ]:
        fund_flow_keys = {
            (flow.holder, flow.asset_key)
            for flow in flows
            if flow.product_type == ProductType.FUND
        }
        by_holder: dict[str, list[AssetSnapshot]] = defaultdict(list)
        for snapshot in snapshots:
            by_holder[snapshot.holder].append(snapshot)

        carried: dict[tuple[str, ProductType, str, str, str], Dezimal] = {}
        sources: set[tuple[str, ProductType, str, str, str]] = set()
        for holder_snapshots in by_holder.values():
            holder_snapshots.sort(key=lambda snapshot: snapshot.moment)
            previous: Optional[dict] = None
            for snapshot in holder_snapshots:
                funds = {
                    valuation.asset_key: valuation
                    for valuation in snapshot.valuations
                    if valuation.product_type == ProductType.FUND
                }
                if previous:
                    for asset_key, valuation in funds.items():
                        if asset_key in previous:
                            continue
                        if (snapshot.holder, asset_key) in fund_flow_keys:
                            continue
                        target_key = self._identity_key(
                            self._valuation_identity(snapshot.holder, valuation)
                        )
                        if target_key in carried:
                            continue
                        match = self._match_vanished_fund(
                            previous, funds, valuation, snapshot.holder, fund_flow_keys
                        )
                        if match is not None:
                            source_key, source_cost = match
                            effective_cost = carried.get(source_key, source_cost)
                            carried[target_key] = effective_cost
                            sources.add(source_key)
                previous = funds
        return carried, sources

    def _match_vanished_fund(
        self,
        previous: dict,
        current: dict,
        new_valuation: AssetValuation,
        holder: str,
        fund_flow_keys: set,
    ) -> Optional[tuple[tuple[str, ProductType, str, str, str], Dezimal]]:
        new_value = new_valuation.market_value
        if new_value is None or new_value <= 0:
            return None
        best_key = None
        best_cost: Optional[Dezimal] = None
        best_diff: Optional[Dezimal] = None
        for asset_key, old_valuation in previous.items():
            if asset_key in current:
                continue
            old_value = old_valuation.market_value
            old_cost = old_valuation.cost_basis
            if old_value is None or old_value <= 0 or old_cost is None:
                continue
            diff = abs(old_value - new_value) / new_value
            if diff > Dezimal("0.05"):
                continue
            if best_diff is None or diff < best_diff:
                best_key = self._identity_key(
                    self._valuation_identity(holder, old_valuation)
                )
                best_cost = old_cost
                best_diff = diff
        if best_key is None or best_cost is None:
            return None
        return best_key, best_cost

    @staticmethod
    def _resolve_transfer_transitions(
        transitions: list[_TransferTransition],
        current_assets: dict[_AssetIdentity, AssetValuation],
    ) -> tuple[set[_AssetIdentity], set[_AssetIdentity]]:
        newly_suppressed: set[_AssetIdentity] = set()
        resolved_targets: set[_AssetIdentity] = set()
        for transition in transitions:
            if transition.resolved:
                continue
            target = current_assets.get(transition.target)
            if (
                target is not None
                and target.quantity is not None
                and target.quantity >= transition.target_required_quantity
            ):
                transition.resolved = True
                newly_suppressed.add(transition.source)
                resolved_targets.add(transition.target)
        return newly_suppressed, resolved_targets

    def _opening_flow(
        self,
        valuation: AssetValuation,
        value: Dezimal,
        flows: list[GainsFlow],
        target_currency: str,
        rates,
    ) -> tuple[Optional[Dezimal], Optional[GainsFlowProvenance]]:
        transaction_quantity, has_unquantified_trade, has_trade = (
            self._transaction_quantity(flows)
        )
        if valuation.quantity is not None and has_trade:
            if has_unquantified_trade:
                return None, None
            residual_quantity = valuation.quantity - transaction_quantity
            if residual_quantity == 0:
                return None, None
            unit_value = self._unit_value(
                valuation.quantity,
                value,
                Dezimal(0),
                Dezimal(0),
            )
            if unit_value is None:
                return None, None
            return residual_quantity * unit_value, GainsFlowProvenance.QUANTITY_RESIDUAL
        if has_trade:
            return None, None
        if valuation.cost_basis is not None:
            converted = self._convert(
                valuation.cost_basis, valuation.currency, target_currency, rates
            )
            if converted is None:
                return None, GainsFlowProvenance.UNKNOWN
            return converted, GainsFlowProvenance.OPENING_BASIS
        return value, GainsFlowProvenance.NET_CONTRIBUTION_FALLBACK

    @staticmethod
    def _unit_value(
        quantity: Dezimal,
        value: Dezimal,
        previous_quantity: Dezimal,
        previous_value: Dezimal,
    ) -> Optional[Dezimal]:
        if quantity != 0:
            return value / quantity
        if previous_quantity != 0:
            return previous_value / previous_quantity
        return None

    @staticmethod
    def _transaction_quantity(flows: list[GainsFlow]) -> tuple[Dezimal, bool, bool]:
        quantity = Dezimal(0)
        has_unquantified_trade = False
        has_trade = False
        for flow in flows:
            if flow.transaction_type not in _POSITION_CHANGING_TYPES:
                continue
            has_trade = True
            if flow.quantity is None:
                has_unquantified_trade = True
                continue
            if flow.transaction_type in _INFLOW_TYPES:
                quantity += flow.quantity
            else:
                quantity -= flow.quantity
        return quantity, has_unquantified_trade, has_trade

    def _valuation_value(
        self,
        identity: _AssetIdentity,
        valuation: AssetValuation,
        day: date,
        accrue_fixed_income: FixedIncomeAccrual,
        target_currency: str,
        rates,
        known_fixed_income_interest_payments: dict[_AssetIdentity, dict[date, Dezimal]],
        recognized_fixed_income_interest_days: dict[_AssetIdentity, set[date]],
        historic: _HistoricRates,
    ) -> Optional[Dezimal]:
        value = self._commodity_value(valuation, day, target_currency, rates, historic)
        if value is None or accrue_fixed_income == FixedIncomeAccrual.NONE:
            return value
        if valuation.product_type not in _FIXED_INCOME_TYPES:
            return value
        if valuation.interest_rate is None or valuation.start_date is None:
            return value
        interest = self._convert(
            self._accrued_interest(
                valuation,
                day,
                known_fixed_income_interest_payments.get(identity, {}),
                recognized_fixed_income_interest_days.get(identity, set()),
            ),
            valuation.currency,
            target_currency,
            rates,
        )
        return value + interest if interest is not None else None

    def _commodity_value(
        self,
        valuation: AssetValuation,
        day: date,
        target_currency: str,
        rates,
        historic: _HistoricRates,
    ) -> Optional[Dezimal]:
        if self._is_historically_revaluable(valuation):
            metal_rates = historic.get(valuation.commodity_type)
            if metal_rates is not None and day < COMMODITY_HISTORIC_CUTOFF:
                ounces = to_troy_ounces(valuation.weight, valuation.weight_unit)
                native_currency = valuation.currency
                if native_currency and native_currency != target_currency:
                    price = metal_rates.price_at(day, native_currency)
                    if price is not None:
                        converted = self._convert(
                            ounces * price,
                            native_currency,
                            target_currency,
                            rates,
                        )
                        if converted is not None:
                            return converted
                price = metal_rates.price_at(day, target_currency)
                if price is not None:
                    return ounces * price
        return self._convert(
            valuation.market_value, valuation.currency, target_currency, rates
        )

    @staticmethod
    def _accrued_interest(
        valuation: AssetValuation,
        day: date,
        known_interest_payments: dict[date, Dezimal],
        recognized_interest_payment_days: set[date],
    ) -> Dezimal:
        if day <= valuation.start_date:
            return Dezimal(0)

        payment_days = sorted(
            payment_day
            for payment_day in known_interest_payments
            if payment_day > valuation.start_date
        )
        if payment_days:
            paid_days = [
                payment_day
                for payment_day in payment_days
                if payment_day <= day
                and payment_day in recognized_interest_payment_days
            ]
            period_start = paid_days[-1] if paid_days else valuation.start_date
            next_payment_days = [
                payment_day
                for payment_day in payment_days
                if payment_day > period_start
            ]
            if next_payment_days:
                next_payment_day = next_payment_days[0]
                if next_payment_day <= day:
                    return known_interest_payments[next_payment_day]
                return (
                    known_interest_payments[next_payment_day]
                    * Dezimal((day - period_start).days)
                    / Dezimal((next_payment_day - period_start).days)
                )
            return GetGainsTimelineImpl._contractual_accrued_interest(
                valuation, day
            ) - GetGainsTimelineImpl._contractual_accrued_interest(
                valuation, period_start
            )

        return GetGainsTimelineImpl._contractual_accrued_interest(valuation, day)

    @staticmethod
    def _contractual_accrued_interest(valuation: AssetValuation, day: date) -> Dezimal:
        if day <= valuation.start_date:
            return Dezimal(0)

        principal = valuation.market_value
        maturity = valuation.maturity
        first_end = min(day, maturity) if maturity is not None else day
        interest = (
            principal
            * valuation.interest_rate
            * Dezimal((first_end - valuation.start_date).days)
            / Dezimal(365)
        )
        if maturity is None or day <= maturity:
            return interest

        extension_end = valuation.extended_maturity or maturity
        if extension_end > maturity:
            extended_end = min(day, extension_end)
            interest += (
                principal
                * (valuation.extended_interest_rate or valuation.interest_rate)
                * Dezimal((extended_end - maturity).days)
                / Dezimal(365)
            )
        if valuation.late_interest_rate is not None and day > extension_end:
            interest += (
                principal
                * valuation.late_interest_rate
                * Dezimal((day - extension_end).days)
                / Dezimal(365)
            )
        return interest

    @staticmethod
    def _known_fixed_income_interest_payments(
        flows: list[GainsFlow], accrual_mode: FixedIncomeAccrual
    ) -> dict[_AssetIdentity, dict[date, Dezimal]]:
        interests: dict[_AssetIdentity, dict[date, Dezimal]] = defaultdict(dict)
        if accrual_mode == FixedIncomeAccrual.NONE:
            return interests
        for flow in flows:
            if (
                flow.product_type not in _FIXED_INCOME_TYPES
                or flow.transaction_type != TxType.INTEREST
            ):
                continue
            amount = flow.amount - flow.fees
            if accrual_mode == FixedIncomeAccrual.NET:
                amount = (
                    flow.net_amount
                    if flow.net_amount is not None
                    else amount - flow.retentions
                )
            identity = GetGainsTimelineImpl._flow_identity(flow)
            day = flow.moment.date()
            interests[identity][day] = interests[identity].get(day, Dezimal(0)) + amount
        return interests

    @staticmethod
    def _period_return(
        value: Dezimal, flow: Dezimal, previous_value: Dezimal
    ) -> Dezimal:
        denominator = previous_value + max(flow, Dezimal(0))
        if denominator <= 0:
            return Dezimal(0)
        return (value - min(flow, Dezimal(0))) / denominator - Dezimal(1)

    @staticmethod
    def _flatten(
        current: dict[str, dict[_AssetIdentity, AssetValuation]],
    ) -> dict[_AssetIdentity, AssetValuation]:
        return {
            identity: valuation
            for holder_assets in current.values()
            for identity, valuation in holder_assets.items()
        }

    @staticmethod
    def _sum_by_type(
        values: dict[_AssetIdentity, Dezimal],
    ) -> dict[ProductType, Dezimal]:
        holder_values: dict[str, dict[ProductType, Dezimal]] = defaultdict(
            lambda: defaultdict(lambda: Dezimal(0))
        )
        for identity, value in values.items():
            holder, product_type = identity[:2]
            holder_values[holder][product_type] += value

        result: dict[ProductType, Dezimal] = defaultdict(lambda: Dezimal(0))
        for values_by_type in holder_values.values():
            for product_type, value in values_by_type.items():
                result[product_type] += value
        return result

    @staticmethod
    def _transaction_cash(
        flow: GainsFlow,
        accrual_mode: FixedIncomeAccrual = FixedIncomeAccrual.NONE,
    ) -> Optional[Dezimal]:
        if flow.transaction_type in _INFLOW_TYPES:
            return flow.amount + flow.fees + flow.retentions
        if flow.transaction_type in _OUTFLOW_TYPES:
            if (
                flow.transaction_type == TxType.INTEREST
                and flow.product_type in _FIXED_INCOME_TYPES
                and accrual_mode == FixedIncomeAccrual.GROSS
            ):
                return -(flow.amount - flow.fees)
            return -(flow.amount - flow.fees - flow.retentions)
        return Dezimal(0)

    def _record_flow(
        self,
        flow: GainsFlow,
        identity: _AssetIdentity,
        period_flows: dict[_AssetIdentity, Dezimal],
        contributions: dict[_AssetIdentity, Dezimal],
        unreconciled_flows: dict[_AssetIdentity, list[GainsFlow]],
        target_currency: str,
        rates,
        accrual_mode: FixedIncomeAccrual,
        provenance: set[GainsFlowProvenance],
        orphan_sell_flow_ids: Optional[set[int]] = None,
    ):
        is_orphan_sell = (
            orphan_sell_flow_ids is not None and id(flow) in orphan_sell_flow_ids
        )
        cash = self._transaction_cash(flow, accrual_mode)
        if cash not in (None, Dezimal(0)) and not is_orphan_sell:
            converted = self._convert(cash, flow.currency, target_currency, rates)
            if converted is not None:
                period_flows[identity] += converted
                contributions[identity] += converted
                provenance.add(GainsFlowProvenance.ACTIVITY)
            else:
                provenance.add(GainsFlowProvenance.UNKNOWN)
        fee_cost = self._fee_cost(flow)
        if fee_cost != 0 and not is_orphan_sell:
            converted_fee = self._convert(
                fee_cost, flow.currency, target_currency, rates
            )
            if converted_fee is not None:
                contributions[identity] += converted_fee
        unreconciled_flows[identity].append(flow)

    def _record_ready_fixed_income_flows(
        self,
        pending_flows: dict[_AssetIdentity, list[GainsFlow]],
        current_assets: dict[_AssetIdentity, AssetValuation],
        period_flows: dict[_AssetIdentity, Dezimal],
        contributions: dict[_AssetIdentity, Dezimal],
        unreconciled_flows: dict[_AssetIdentity, list[GainsFlow]],
        previous_assets: dict[_AssetIdentity, AssetValuation],
        observed_assets: set[_AssetIdentity],
        target_currency: str,
        rates,
        accrual_mode: FixedIncomeAccrual,
        provenance: set[GainsFlowProvenance],
    ) -> list[GainsFlow]:
        recorded_flows: list[GainsFlow] = []
        for identity, flows in list(pending_flows.items()):
            asset_exists = identity in current_assets
            has_repayment = any(
                flow.transaction_type == TxType.REPAYMENT for flow in flows
            )
            if asset_exists and not has_repayment:
                ready_flows = flows
            elif not asset_exists and has_repayment:
                ready_flows = (
                    [
                        flow
                        for flow in flows
                        if flow.transaction_type != TxType.INVESTMENT
                    ]
                    if identity in observed_assets
                    else flows
                )
            elif asset_exists and has_repayment:
                previous = previous_assets.get(identity)
                repayment_total = sum(
                    (
                        flow.amount
                        for flow in flows
                        if flow.transaction_type == TxType.REPAYMENT
                    ),
                    Dezimal(0),
                )
                principal_reduction = (
                    previous.market_value - current_assets[identity].market_value
                    if previous is not None
                    else Dezimal(0)
                )
                if principal_reduction + Dezimal("0.01") >= repayment_total:
                    ready_flows = flows
                else:
                    continue
            else:
                continue
            for flow in ready_flows:
                self._record_flow(
                    flow,
                    identity,
                    period_flows,
                    contributions,
                    unreconciled_flows,
                    target_currency,
                    rates,
                    accrual_mode,
                    provenance,
                )
                recorded_flows.append(flow)
            remaining_flows = [flow for flow in flows if flow not in ready_flows]
            if remaining_flows:
                pending_flows[identity] = remaining_flows
            else:
                del pending_flows[identity]
        return recorded_flows

    @staticmethod
    def _has_unobserved_inflow(
        unreconciled_flows: dict[_AssetIdentity, list[GainsFlow]],
        pending_fixed_income_flows: dict[_AssetIdentity, list[GainsFlow]],
        since: Optional[date] = None,
    ) -> bool:
        return any(
            flow.transaction_type in _INFLOW_TYPES
            and (since is None or flow.moment.date() >= since)
            for flow_groups in (
                unreconciled_flows.values(),
                pending_fixed_income_flows.values(),
            )
            for flows in flow_groups
            for flow in flows
        )

    @staticmethod
    def _fee_cost(flow: GainsFlow) -> Dezimal:
        if flow.transaction_type == TxType.FEE:
            return flow.amount + flow.fees + flow.retentions
        return Dezimal(0)

    @staticmethod
    def _matches(
        product_type: ProductType,
        asset_key: str,
        filters: list[GainsAssetFilter],
        portfolio_name: Optional[str] = None,
        equity_type: Optional[EquityType] = None,
        wallet_id: Optional[UUID] = None,
    ) -> bool:
        return any(
            product_type == asset_filter.product_type
            and (
                not asset_filter.asset_keys
                or asset_key in asset_filter.asset_keys
                or (
                    product_type == ProductType.COMMODITY
                    and any(
                        asset_key.startswith(f"{filter_key}:")
                        for filter_key in asset_filter.asset_keys
                    )
                )
            )
            and (
                not asset_filter.portfolio_names
                or portfolio_name in asset_filter.portfolio_names
            )
            and (
                not asset_filter.equity_types
                or equity_type in asset_filter.equity_types
            )
            and (not asset_filter.wallet_ids or wallet_id in asset_filter.wallet_ids)
            for asset_filter in filters
        )

    def _cache_key(
        self,
        query: GainsTimelineQuery,
        entity_ids: list[str],
        rates,
        as_of: date,
    ) -> str:
        assets = [
            ":".join(
                (
                    asset.product_type.value,
                    ",".join(sorted(asset.asset_keys)),
                    ",".join(sorted(asset.portfolio_names)),
                    ",".join(
                        sorted(equity_type.value for equity_type in asset.equity_types)
                    ),
                    ",".join(sorted(str(wallet_id) for wallet_id in asset.wallet_ids)),
                )
            )
            for asset in sorted(
                query.assets, key=lambda asset: asset.product_type.value
            )
        ]
        rate_parts = []
        for target_currency in sorted(rates):
            for source_currency in sorted(rates[target_currency]):
                rate_parts.append(
                    f"{target_currency}:{source_currency}:{rates[target_currency][source_currency]}"
                )
        raw = "|".join(
            [
                query.base_currency,
                ",".join(assets),
                ",".join(entity_ids),
                query.accrue_fixed_income.value,
                query.calculation_mode.value,
                as_of.isoformat(),
                query.from_date.isoformat() if query.from_date else "",
                query.to_date.isoformat() if query.to_date else "",
                ",".join(rate_parts),
            ]
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def _slice(
        self, timeline: GainsTimeline, query: GainsTimelineQuery
    ) -> GainsTimeline:
        upper = min(
            query.to_date or date.max,
            datetime.now(tzlocal()).date() - timedelta(days=1),
        )
        points = [
            point
            for point in timeline.points
            if point.date <= upper
            and (query.from_date is None or point.date >= query.from_date)
        ]
        if not points:
            return GainsTimeline(
                currency=timeline.currency,
                method=timeline.method,
                basis=timeline.basis,
                quality=timeline.quality,
                basis_status=timeline.basis_status,
                xirr=timeline.xirr,
                annualized_xirr=timeline.annualized_xirr,
                opening_value=timeline.opening_value,
                warnings=timeline.warnings,
                not_applicable_reasons=timeline.not_applicable_reasons,
            )

        total_base = points[0].metrics.index
        bucket_bases = {
            product_type: metrics.index
            for product_type, metrics in points[0].breakdown.items()
        }
        return GainsTimeline(
            currency=timeline.currency,
            points=[
                GainsTimelinePoint(
                    date=point.date,
                    metrics=self._copy_metrics(point.metrics, total_base),
                    breakdown={
                        product_type: self._copy_metrics(
                            metrics,
                            bucket_bases.setdefault(product_type, metrics.index),
                        )
                        for product_type, metrics in point.breakdown.items()
                    },
                )
                for point in points
            ],
            method=timeline.method,
            basis=timeline.basis,
            quality=timeline.quality,
            basis_status=timeline.basis_status,
            xirr=timeline.xirr,
            annualized_xirr=timeline.annualized_xirr,
            opening_value=timeline.opening_value,
            warnings=timeline.warnings,
            not_applicable_reasons=timeline.not_applicable_reasons,
        )

    @staticmethod
    def _copy_metrics(
        metrics: GainsMetrics, index_base: Optional[Dezimal]
    ) -> GainsMetrics:
        index = metrics.index
        if index is not None:
            index = (index * Dezimal(100) / index_base) if index_base else Dezimal(100)
        return GainsMetrics(
            value=metrics.value,
            cost_basis=metrics.cost_basis,
            net_contributions=metrics.net_contributions,
            gain=metrics.gain,
            period_return=metrics.period_return,
            index=index,
        )

    def _convert(
        self,
        value: Dezimal,
        source_currency: Optional[str],
        target_currency: str,
        rates,
    ) -> Optional[Dezimal]:
        if not source_currency or source_currency == target_currency:
            return value
        try:
            rate = rates[target_currency][source_currency]
        except KeyError:
            self._log.warning(
                "Missing exchange rate %s->%s for gains timeline",
                source_currency,
                target_currency,
            )
            return None
        if rate == 0:
            return None
        return value / rate
