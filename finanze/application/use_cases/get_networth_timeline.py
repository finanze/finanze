import asyncio
import hashlib
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from application.ports.config_port import ConfigPort
from application.ports.entity_port import EntityPort
from application.ports.exchange_rate_storage import ExchangeRateStorage
from application.ports.networth_timeline_port import NetworthTimelinePort
from application.ports.real_estate_port import RealEstatePort
from dateutil.tz import tzlocal
from domain.dezimal import Dezimal
from domain.exchange_rate import ExchangeRates
from domain.global_position import ProductType
from domain.networth_timeline import (
    REAL_ESTATE_BUCKET,
    REAL_ESTATE_RESIDENCE_BUCKET,
    NetworthTimeline,
    NetworthTimelinePoint,
    NetworthTimelineQuery,
    NetworthTimelineState,
    PositionSnapshot,
)
from domain.real_estate import RealEstate, RealEstateFlowSubtype
from domain.use_cases.get_networth_timeline import GetNetworthTimeline

_DEBT_TYPES = {ProductType.CARD, ProductType.LOAN, ProductType.CREDIT}


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
    def __init__(
        self,
        networth_timeline_port: NetworthTimelinePort,
        exchange_rate_storage: ExchangeRateStorage,
        config_port: ConfigPort,
        entity_port: EntityPort,
        real_estate_port: RealEstatePort,
    ):
        self._port = networth_timeline_port
        self._exchange_rate_storage = exchange_rate_storage
        self._config_port = config_port
        self._entity_port = entity_port
        self._real_estate_port = real_estate_port
        self._lock = asyncio.Lock()
        self._log = logging.getLogger(__name__)

    async def execute(self, query: NetworthTimelineQuery) -> NetworthTimeline:
        settings = await self._config_port.load()
        target_currency = settings.general.defaultCurrency
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

        signature = self._signature(
            target_currency, excluded_ids, mortgage_refs, snapshots
        )
        state = await self._port.get_state()
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

        max_snapshot_day = max(s.moment.date() for s in snapshots)
        if not wipe and last_computed is not None and last_computed >= max_snapshot_day:
            return

        all_points = self._carry_forward(
            snapshots, mortgage_refs, target_currency, rates, yesterday
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
                inputs_signature=signature, last_computed_date=max_snapshot_day
            ),
            wipe,
        )

    def _snapshot_breakdown(
        self,
        snapshot: PositionSnapshot,
        mortgage_refs: set[str],
        target_currency: str,
        rates: ExchangeRates,
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

    def _carry_forward(
        self,
        snapshots: list[PositionSnapshot],
        mortgage_refs: set[str],
        target_currency: str,
        rates: ExchangeRates,
        yesterday: date,
    ) -> list[NetworthTimelinePoint]:
        breakdown_of: dict[int, dict[str, Dezimal]] = {
            id(snapshot): self._snapshot_breakdown(
                snapshot, mortgage_refs, target_currency, rates
            )
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

        current: dict[str, PositionSnapshot] = {}
        points: list[NetworthTimelinePoint] = []
        current_import_batch: Optional[str] = None
        for day in sorted(days):
            for snapshot in sorted(by_day.get(day, []), key=lambda s: s.moment):
                # Sources whose every import fully re-declares the portfolio
                # (Sheets) carry an import batch. A newer batch replaces all
                # prior batched holders, so anything missing from it stops
                # contributing from this import day on.
                if (
                    snapshot.import_batch is not None
                    and snapshot.import_batch != current_import_batch
                ):
                    current = {
                        holder: held
                        for holder, held in current.items()
                        if held.import_batch is None
                    }
                    current_import_batch = snapshot.import_batch
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
                if (
                    flow.flow_subtype != RealEstateFlowSubtype.LOAN
                    or not flow.linked_loan_hash
                ):
                    continue
                loan_ref = flow.linked_loan_hash
                snaps = self._collapse_daily(outstanding_by_ref.get(loan_ref, []))
                anchor = purchase_date
                origination = origination_by_ref.get(loan_ref)
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
        snapshots: list[PositionSnapshot] = (),
    ) -> str:
        deleted_holders = sorted(
            f"{s.holder}:{s.holder_deleted_at.isoformat()}"
            for s in snapshots
            if s.holder_deleted_at is not None
        )
        import_batches = sorted(
            {s.import_batch for s in snapshots if s.import_batch is not None}
        )
        raw = "|".join(
            [
                target_currency,
                ",".join(excluded_ids),
                ",".join(sorted(mortgage_refs)),
                ",".join(deleted_holders),
                ",".join(import_batches),
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
