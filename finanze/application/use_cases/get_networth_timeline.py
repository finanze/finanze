import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from application.ports.entity_port import EntityPort
from application.ports.exchange_rate_storage import ExchangeRateStorage
from application.ports.metal_price_provider import MetalPriceProvider
from application.ports.networth_timeline_port import NetworthTimelinePort
from application.ports.real_estate_port import RealEstatePort
from dateutil.tz import tzlocal
from domain.commodity import CommodityType, to_troy_ounces
from domain.dezimal import Dezimal
from domain.exchange_rate import ExchangeRates, HistoricMetalRates
from domain.global_position import ProductType
from domain.networth_timeline import (
    COMMODITY_HISTORIC_CUTOFF,
    REAL_ESTATE_BUCKET,
    REAL_ESTATE_RESIDENCE_BUCKET,
    HoldingValuation,
    NetworthTimeline,
    NetworthTimelinePoint,
    NetworthTimelineQuery,
    NetworthTimelineState,
    PositionSnapshot,
)
from domain.real_estate import RealEstate, RealEstateFlowSubtype
from domain.use_cases.get_networth_timeline import GetNetworthTimeline

_DEBT_TYPES = {ProductType.CARD, ProductType.LOAN, ProductType.CREDIT}

_HistoricRates = dict[CommodityType, Optional[HistoricMetalRates]]


class _PropertyModel:
    def __init__(
        self,
        purchase_date: date,
        value_breakpoints: list[tuple[date, Dezimal]],
        mortgages: list[dict],
        is_residence: bool,
    ):
        self.purchase_date = purchase_date
        self.value_breakpoints = value_breakpoints
        self.mortgages = mortgages
        self.is_residence = is_residence


class GetNetworthTimelineImpl(GetNetworthTimeline):
    RE_SERIES_CACHE_TTL_SECONDS = 60 * 60

    def __init__(
        self,
        networth_timeline_port: NetworthTimelinePort,
        exchange_rate_storage: ExchangeRateStorage,
        entity_port: EntityPort,
        real_estate_port: RealEstatePort,
        metal_price_provider: MetalPriceProvider,
    ):
        self._port = networth_timeline_port
        self._exchange_rate_storage = exchange_rate_storage
        self._entity_port = entity_port
        self._real_estate_port = real_estate_port
        self._metal_price_provider = metal_price_provider
        self._lock = asyncio.Lock()
        self._re_series_cache: Optional[
            tuple[str, float, list[tuple[date, dict[str, Dezimal]]]]
        ] = None
        self._log = logging.getLogger(__name__)

    async def execute(self, query: NetworthTimelineQuery) -> NetworthTimeline:
        target_currency = query.base_currency
        disabled = await self._entity_port.get_disabled_entities()
        excluded_ids = sorted(str(e.id) for e in disabled)

        real_estate_list = await self._real_estate_port.get_all()
        mortgage_refs = self._collect_mortgage_refs(real_estate_list)

        rates = await self._exchange_rate_storage.get()
        yesterday = datetime.now(tzlocal()).date() - timedelta(days=1)

        if not query.no_calculation and not self._lock.locked():
            async with self._lock:
                await self._compute_and_persist(
                    target_currency, excluded_ids, mortgage_refs, rates, yesterday
                )

        memo_points = await self._port.get_points(None, query.to_date)
        re_series = await self._build_real_estate_series(
            real_estate_list, mortgage_refs, target_currency, rates
        )

        points = self._merge(
            memo_points, re_series, query.from_date, query.to_date, yesterday
        )
        return NetworthTimeline(currency=target_currency, points=points)

    # --- Memoized positions computation ---

    async def _compute_and_persist(
        self,
        target_currency: str,
        excluded_ids: list[str],
        mortgage_refs: set[str],
        rates: ExchangeRates,
        yesterday: date,
    ):
        snapshots = await self._port.get_position_snapshots(excluded_ids)
        snapshots = [s for s in snapshots if s.moment.date() <= yesterday]

        state = await self._port.get_state()
        base_signature = self._signature(
            target_currency, excluded_ids, mortgage_refs, snapshots
        )
        historic, historic_part = await self._resolve_historic_rates(
            snapshots, state, base_signature, yesterday
        )
        signature = (
            f"{base_signature}|{historic_part}" if historic_part else base_signature
        )
        wipe = state.inputs_signature != signature
        last_computed = None if wipe else state.last_computed_date

        if not snapshots:
            if wipe:
                await self._port.persist(
                    [],
                    target_currency,
                    NetworthTimelineState(inputs_signature=signature),
                    wipe=True,
                )
            return

        commodity_days = self._commodity_days(snapshots, historic, yesterday)
        max_day = max(s.moment.date() for s in snapshots)
        if commodity_days:
            max_day = max(max_day, max(commodity_days))
        if not wipe and last_computed is not None and last_computed >= max_day:
            return

        all_points = self._carry_forward(
            snapshots,
            mortgage_refs,
            target_currency,
            rates,
            yesterday,
            historic,
            commodity_days,
        )

        if wipe:
            points_to_persist = all_points
        else:
            points_to_persist = [
                p for p in all_points if last_computed is None or p.date > last_computed
            ]

        await self._port.persist(
            points_to_persist,
            target_currency,
            NetworthTimelineState(
                inputs_signature=signature, last_computed_date=max_day
            ),
            wipe,
        )

    def _snapshot_breakdown(
        self,
        snapshot: PositionSnapshot,
        mortgage_refs: set[str],
        target_currency: str,
        rates: ExchangeRates,
        historic: _HistoricRates,
    ) -> dict[str, Dezimal]:
        breakdown: dict[str, Dezimal] = {}
        for holding in snapshot.holdings:
            # A property-linked mortgage is already netted into real estate
            # equity, so it must not also be counted in the loan debt bucket.
            if (
                holding.product_type == ProductType.LOAN
                and holding.loan_ref
                and holding.loan_ref in mortgage_refs
            ):
                continue
            # Revaluable commodities are valued per day from historic prices.
            if self._is_revaluable(holding, historic):
                continue
            converted = self._convert(
                holding.amount,
                holding.currency or target_currency,
                target_currency,
                rates,
            )
            if converted is None:
                continue
            if holding.product_type in _DEBT_TYPES:
                converted = -converted
            key = holding.product_type.value
            breakdown[key] = breakdown.get(key, Dezimal(0)) + converted
        return breakdown

    # --- Commodity revaluation from historic metal prices ---

    async def _resolve_historic_rates(
        self,
        snapshots: list[PositionSnapshot],
        state: NetworthTimelineState,
        base_signature: str,
        yesterday: date,
    ) -> tuple[_HistoricRates, str]:
        types = sorted(
            {
                holding.commodity_type
                for snapshot in snapshots
                if snapshot.moment.date() < COMMODITY_HISTORIC_CUTOFF
                for holding in snapshot.holdings
                if holding.product_type == ProductType.COMMODITY
                and holding.commodity_type is not None
                and holding.weight is not None
                and holding.weight_unit is not None
            },
            key=lambda t: t.value,
        )
        if not types:
            return {}, ""

        # Once every pre-cutoff day is memoized with all datasets available,
        # the static historic data can add nothing new, so the fetch is skipped.
        complete_part = ",".join(f"{t.value}:present" for t in types)
        upper = min(yesterday, COMMODITY_HISTORIC_CUTOFF - timedelta(days=1))
        if (
            state.inputs_signature == f"{base_signature}|{complete_part}"
            and state.last_computed_date is not None
            and state.last_computed_date >= upper
        ):
            return {}, complete_part

        results = await asyncio.gather(
            *(self._metal_price_provider.get_partial_historic_rates(t) for t in types)
        )
        historic = dict(zip(types, results))
        part = ",".join(
            f"{t.value}:present" if r is not None and r.days else f"{t.value}:missing"
            for t, r in historic.items()
        )
        return historic, part

    @staticmethod
    def _is_revaluable(holding: HoldingValuation, historic: _HistoricRates) -> bool:
        return (
            holding.product_type == ProductType.COMMODITY
            and holding.commodity_type is not None
            and holding.weight is not None
            and holding.weight_unit is not None
            and historic.get(holding.commodity_type) is not None
        )

    def _commodity_days(
        self,
        snapshots: list[PositionSnapshot],
        historic: _HistoricRates,
        yesterday: date,
    ) -> set[date]:
        first: Optional[date] = None
        types: set[CommodityType] = set()
        for snapshot in snapshots:
            revaluable = [
                h for h in snapshot.holdings if self._is_revaluable(h, historic)
            ]
            if not revaluable:
                continue
            day = snapshot.moment.date()
            if first is None or day < first:
                first = day
            types.update(h.commodity_type for h in revaluable)
        if first is None:
            return set()

        upper = min(yesterday, COMMODITY_HISTORIC_CUTOFF - timedelta(days=1))
        days: set[date] = set()
        for commodity_type in types:
            rates = historic.get(commodity_type)
            if rates is None:
                continue
            days.update(d for d in rates.days if first <= d <= upper)
        return days

    def _commodity_value_at(
        self,
        holding: HoldingValuation,
        day: date,
        historic: _HistoricRates,
        target_currency: str,
        rates: ExchangeRates,
    ) -> Optional[Dezimal]:
        metal_rates = historic.get(holding.commodity_type)
        if metal_rates is not None and day < COMMODITY_HISTORIC_CUTOFF:
            ounces = to_troy_ounces(holding.weight, holding.weight_unit)
            native = holding.currency
            if native and native != target_currency:
                price = metal_rates.price_at(day, native)
                if price is not None:
                    converted = self._convert(
                        ounces * price, native, target_currency, rates
                    )
                    if converted is not None:
                        return converted
            price = metal_rates.price_at(day, target_currency)
            if price is not None:
                return ounces * price
        return self._convert(
            holding.amount,
            holding.currency or target_currency,
            target_currency,
            rates,
        )

    def _carry_forward(
        self,
        snapshots: list[PositionSnapshot],
        mortgage_refs: set[str],
        target_currency: str,
        rates: ExchangeRates,
        yesterday: date,
        historic: _HistoricRates,
        commodity_days: set[date],
    ) -> list[NetworthTimelinePoint]:
        breakdown_of: dict[int, dict[str, Dezimal]] = {
            id(snapshot): self._snapshot_breakdown(
                snapshot, mortgage_refs, target_currency, rates, historic
            )
            for snapshot in snapshots
        }
        revaluable_of: dict[int, list[HoldingValuation]] = {
            id(snapshot): [
                h for h in snapshot.holdings if self._is_revaluable(h, historic)
            ]
            for snapshot in snapshots
        }

        by_day: dict[date, list[PositionSnapshot]] = defaultdict(list)
        for snapshot in snapshots:
            by_day[snapshot.moment.date()].append(snapshot)

        # Holder deletions become explicit breakpoints so the drop in net worth
        # is visible even on days without a snapshot (e.g. an account deleted
        # between two snapshots, or deleted and later re-added).
        first_day = min(by_day.keys())
        days = set(by_day.keys())
        for snapshot in snapshots:
            deleted_at = snapshot.holder_deleted_at
            if deleted_at is not None and first_day < deleted_at <= yesterday:
                days.add(deleted_at)
        # Historic metal price days densify the series so commodity values vary
        # daily even where no position snapshot exists.
        days.update(commodity_days)

        current: dict[str, PositionSnapshot] = {}
        points: list[NetworthTimelinePoint] = []
        for day in sorted(days):
            for snapshot in sorted(by_day.get(day, []), key=lambda s: s.moment):
                current[snapshot.holder] = snapshot

            breakdown: dict[str, Dezimal] = {}
            for snapshot in current.values():
                # A soft-deleted holder stops contributing from its deletion day
                # onwards; its stale positions linger in the DB but no longer
                # represent owned assets.
                if (
                    snapshot.holder_deleted_at is not None
                    and day >= snapshot.holder_deleted_at
                ):
                    continue
                for product_type, value in breakdown_of[id(snapshot)].items():
                    breakdown[product_type] = (
                        breakdown.get(product_type, Dezimal(0)) + value
                    )
                for holding in revaluable_of[id(snapshot)]:
                    value = self._commodity_value_at(
                        holding, day, historic, target_currency, rates
                    )
                    if value is None:
                        continue
                    key = holding.product_type.value
                    breakdown[key] = breakdown.get(key, Dezimal(0)) + value
            total = sum(breakdown.values(), Dezimal(0))
            points.append(
                NetworthTimelinePoint(date=day, total=total, breakdown=breakdown)
            )
        return points

    # --- Real estate (computed on the fly) ---

    async def _build_real_estate_series(
        self,
        real_estate_list: list[RealEstate],
        mortgage_refs: set[str],
        target_currency: str,
        rates: ExchangeRates,
    ) -> list[tuple[date, dict[str, Dezimal]]]:
        if not real_estate_list:
            return []

        # The real estate series is not memoized in the database, so rebuilding
        # it (a mortgage valuation query plus breakpoint assembly) on every call
        # dominates the endpoint cost. It is independent of the requested date
        # range, so a single full series is cached and sliced per request. The
        # signature invalidates on real estate edits; the TTL refreshes the
        # parts sourced from the DB (mortgage valuation snapshots) and rates.
        signature = self._real_estate_cache_signature(
            real_estate_list, mortgage_refs, target_currency
        )
        now = time.monotonic()
        cached = self._re_series_cache
        if cached is not None and cached[0] == signature and cached[1] > now:
            return cached[2]

        series = await self._compute_real_estate_series(
            real_estate_list, mortgage_refs, target_currency, rates
        )
        self._re_series_cache = (
            signature,
            now + self.RE_SERIES_CACHE_TTL_SECONDS,
            series,
        )
        return series

    def _real_estate_cache_signature(
        self,
        real_estate_list: list[RealEstate],
        mortgage_refs: set[str],
        target_currency: str,
    ) -> str:
        parts = [target_currency, ",".join(sorted(mortgage_refs))]
        for real_estate in real_estate_list:
            flows: list[str] = []
            for flow in real_estate.flows:
                if flow.flow_subtype != RealEstateFlowSubtype.LOAN:
                    continue
                outstanding = getattr(flow.payload, "principal_outstanding", None)
                flows.append(
                    f"{flow.linked_loan_hash or ''}:"
                    f"{'' if outstanding is None else outstanding}"
                )
            parts.append(
                "#".join(
                    [
                        str(getattr(real_estate, "id", None)),
                        real_estate.purchase_info.date.isoformat(),
                        str(real_estate.purchase_info.price),
                        str(real_estate.valuation_info.estimated_market_value),
                        real_estate.currency,
                        "1" if real_estate.basic_info.is_residence else "0",
                        ";".join(sorted(flows)),
                    ]
                )
            )
        return hashlib.sha256("|".join(parts).encode()).hexdigest()

    async def _compute_real_estate_series(
        self,
        real_estate_list: list[RealEstate],
        mortgage_refs: set[str],
        target_currency: str,
        rates: ExchangeRates,
    ) -> list[tuple[date, dict[str, Dezimal]]]:
        mortgage_valuations = await self._port.get_mortgage_valuations(
            sorted(mortgage_refs)
        )
        outstanding_by_ref: dict[str, list[tuple[date, Dezimal]]] = defaultdict(list)
        origination_by_ref: dict[str, date] = {}
        for valuation in mortgage_valuations:
            converted = self._convert(
                valuation.outstanding, valuation.currency, target_currency, rates
            )
            if converted is None:
                converted = Dezimal(0)
            outstanding_by_ref[valuation.loan_ref].append(
                (valuation.moment.date(), converted)
            )
            if valuation.origination and valuation.loan_ref not in origination_by_ref:
                origination_by_ref[valuation.loan_ref] = valuation.origination

        property_models: list[_PropertyModel] = []
        breakpoint_days: set[date] = set()
        for real_estate in real_estate_list:
            purchase_date = real_estate.purchase_info.date
            value_breakpoints = self._build_value_breakpoints(
                real_estate, target_currency, rates
            )
            for day, _ in value_breakpoints:
                breakpoint_days.add(day)
            breakpoint_days.add(purchase_date)

            mortgages = []
            for flow in real_estate.flows:
                if flow.flow_subtype != RealEstateFlowSubtype.LOAN:
                    continue
                loan_ref = flow.linked_loan_hash
                snaps = (
                    self._collapse_daily(outstanding_by_ref.get(loan_ref, []))
                    if loan_ref
                    else []
                )
                anchor = purchase_date
                origination = origination_by_ref.get(loan_ref) if loan_ref else None
                if origination and origination > anchor:
                    anchor = origination
                fallback_outstanding = None
                raw_outstanding = getattr(flow.payload, "principal_outstanding", None)
                if raw_outstanding is not None:
                    fallback_outstanding = self._convert(
                        raw_outstanding, real_estate.currency, target_currency, rates
                    )
                mortgages.append(
                    {
                        "snaps": snaps,
                        "anchor": anchor,
                        "fallback": fallback_outstanding,
                    }
                )
                for day, _ in snaps:
                    breakpoint_days.add(day)
                breakpoint_days.add(anchor)

            property_models.append(
                _PropertyModel(
                    purchase_date,
                    value_breakpoints,
                    mortgages,
                    bool(real_estate.basic_info.is_residence),
                )
            )

        if not breakpoint_days:
            return []

        series: list[tuple[date, dict[str, Dezimal]]] = []
        for day in sorted(breakpoint_days):
            buckets: dict[str, Dezimal] = {
                REAL_ESTATE_BUCKET: Dezimal(0),
                REAL_ESTATE_RESIDENCE_BUCKET: Dezimal(0),
            }
            for model in property_models:
                value = self._value_at(model.value_breakpoints, day)
                outstanding = Dezimal(0)
                for mortgage in model.mortgages:
                    outstanding += self._outstanding_at(mortgage, day)
                bucket = (
                    REAL_ESTATE_RESIDENCE_BUCKET
                    if model.is_residence
                    else REAL_ESTATE_BUCKET
                )
                buckets[bucket] += value - outstanding
            series.append((day, buckets))
        return series

    def _build_value_breakpoints(
        self,
        real_estate: RealEstate,
        target_currency: str,
        rates: ExchangeRates,
    ) -> list[tuple[date, Dezimal]]:
        purchase_date = real_estate.purchase_info.date
        value = self._convert(
            real_estate.valuation_info.estimated_market_value,
            real_estate.currency,
            target_currency,
            rates,
        )
        if value is None:
            value = self._convert(
                real_estate.purchase_info.price,
                real_estate.currency,
                target_currency,
                rates,
            )
        return [(purchase_date, value if value is not None else Dezimal(0))]

    @staticmethod
    def _value_at(breakpoints: list[tuple[date, Dezimal]], day: date) -> Dezimal:
        value = Dezimal(0)
        for break_day, break_value in breakpoints:
            if break_day <= day:
                value = break_value
            else:
                break
        return value

    @staticmethod
    def _outstanding_at(mortgage: dict, day: date) -> Dezimal:
        anchor = mortgage["anchor"]
        if day < anchor:
            return Dezimal(0)
        snaps = mortgage["snaps"]
        if not snaps:
            return (
                mortgage["fallback"] if mortgage["fallback"] is not None else Dezimal(0)
            )
        if day < snaps[0][0]:
            return snaps[0][1]
        value = snaps[0][1]
        for snap_day, snap_value in snaps:
            if snap_day <= day:
                value = snap_value
            else:
                break
        return value

    @staticmethod
    def _collapse_daily(
        rows: list[tuple[date, Dezimal]],
    ) -> list[tuple[date, Dezimal]]:
        by_day: dict[date, Dezimal] = {}
        for day, value in rows:
            by_day[day] = value
        return sorted(by_day.items())

    # --- Merge ---

    def _merge(
        self,
        memo_points: list[NetworthTimelinePoint],
        re_series: list[tuple[date, dict[str, Dezimal]]],
        from_date: Optional[date],
        to_date: Optional[date],
        yesterday: date,
    ) -> list[NetworthTimelinePoint]:
        upper = yesterday
        if to_date is not None and to_date < upper:
            upper = to_date

        memo_sorted = [p for p in memo_points if p.date <= upper]
        re_sorted = [(d, e) for (d, e) in re_series if d <= upper]

        day_set: set[date] = {p.date for p in memo_sorted}
        day_set.update(d for d, _ in re_sorted)
        if from_date is not None:
            day_set = {d for d in day_set if d >= from_date}
        output_days = sorted(day_set)
        if not output_days:
            return []

        points: list[NetworthTimelinePoint] = []
        memo_index = 0
        re_index = 0
        current_memo: Optional[NetworthTimelinePoint] = None
        current_re: dict[str, Dezimal] = {}
        re_active = False
        for day in output_days:
            while memo_index < len(memo_sorted) and memo_sorted[memo_index].date <= day:
                current_memo = memo_sorted[memo_index]
                memo_index += 1
            while re_index < len(re_sorted) and re_sorted[re_index][0] <= day:
                current_re = re_sorted[re_index][1]
                re_index += 1
                re_active = True

            breakdown: dict[str, Dezimal] = (
                dict(current_memo.breakdown) if current_memo else {}
            )
            memo_total = current_memo.total if current_memo else Dezimal(0)
            re_total = Dezimal(0)
            if re_active:
                for bucket, amount in current_re.items():
                    breakdown[bucket] = amount
                    re_total += amount
            total = memo_total + re_total
            points.append(
                NetworthTimelinePoint(date=day, total=total, breakdown=breakdown)
            )
        return points

    # --- Helpers ---

    def _collect_mortgage_refs(self, real_estate_list: list[RealEstate]) -> set[str]:
        refs: set[str] = set()
        for real_estate in real_estate_list:
            for flow in real_estate.flows:
                if (
                    flow.flow_subtype == RealEstateFlowSubtype.LOAN
                    and flow.linked_loan_hash
                ):
                    refs.add(flow.linked_loan_hash)
        return refs

    @staticmethod
    def _signature(
        target_currency: str,
        excluded_ids: list[str],
        mortgage_refs: set[str],
        snapshots: list[PositionSnapshot],
    ) -> str:
        deleted_holders = sorted(
            f"{s.holder}:{s.holder_deleted_at.isoformat()}"
            for s in snapshots
            if s.holder_deleted_at is not None
        )
        # A re-declaring import retroactively defines the portfolio of its
        # source from its day on, so changes to the set of imports must force a
        # full recomputation.
        import_markers = sorted(
            f"{s.holder}:{s.moment.isoformat()}" for s in snapshots if s.redeclaring
        )
        raw = "|".join(
            [
                target_currency,
                ",".join(excluded_ids),
                ",".join(sorted(mortgage_refs)),
                ",".join(deleted_holders),
                ",".join(import_markers),
            ]
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def _convert(
        self,
        value: Dezimal,
        source_currency: Optional[str],
        target_currency: str,
        rates: ExchangeRates,
    ) -> Optional[Dezimal]:
        if not source_currency or source_currency == target_currency:
            return value
        try:
            rate = rates[target_currency][source_currency]
        except KeyError:
            self._log.warning(
                "Missing exchange rate %s->%s for net worth timeline",
                source_currency,
                target_currency,
            )
            return None
        if rate == 0:
            return None
        return value / rate
