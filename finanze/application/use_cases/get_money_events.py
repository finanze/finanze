from datetime import date, timedelta
from typing import Iterable
from uuid import UUID

from application.ports.entity_port import EntityPort
from application.ports.position_port import PositionPort
from application.use_cases.get_contributions import _contrib_freq_delta_map
from application.use_cases.get_periodic_flows import frequency_delta_map
from dateutil.relativedelta import relativedelta
from domain.auto_contributions import (
    AutoContributions,
    ContributionFrequency,
    ContributionQueryRequest,
)
from domain.dezimal import Dezimal
from domain.earnings_expenses import (
    FlowFrequency,
    FlowType,
    PendingFlow,
    PeriodicFlow,
)
from domain.global_position import (
    Deposits,
    FactoringInvestments,
    PositionQueryRequest,
    ProductType,
    RealEstateCFDetail,
    RealEstateCFInvestments,
)
from domain.money_event import (
    MoneyEvent,
    MoneyEventFrequency,
    MoneyEventQuery,
    MoneyEvents,
    MoneyEventType,
    PeriodicContributionDetails,
)
from domain.use_cases.get_contributions import GetContributions
from domain.use_cases.get_money_events import GetMoneyEvents
from domain.use_cases.get_pending_flows import GetPendingFlows
from domain.use_cases.get_periodic_flows import GetPeriodicFlows


class GetMoneyEventsImpl(GetMoneyEvents):
    def __init__(
        self,
        get_contributions_uc: GetContributions,
        get_periodic_flows_uc: GetPeriodicFlows,
        get_pending_flows_uc: GetPendingFlows,
        entity_port: EntityPort,
        position_port: PositionPort,
    ):
        self._get_contributions = get_contributions_uc
        self._get_periodic_flows = get_periodic_flows_uc
        self._get_pending_flows = get_pending_flows_uc
        self._entity_port = entity_port
        self._position_port = position_port

    def execute(self, query: MoneyEventQuery) -> MoneyEvents:
        disabled_entities = [
            entity.id for entity in self._entity_port.get_disabled_entities()
        ]
        contribution_query = ContributionQueryRequest(
            excluded_entities=disabled_entities or None,
        )
        contributions = self._get_contributions.execute(contribution_query)
        periodic_flows = self._get_periodic_flows.execute()
        pending_flows = self._get_pending_flows.execute()

        contribution_events = self._build_contribution_events(
            contributions.contributions.values(), query
        )
        periodic_flow_events = self._build_periodic_flow_events(periodic_flows, query)
        pending_flow_events = self._build_pending_flow_events(pending_flows, query)
        maturity_events = self._build_maturity_events(query, disabled_entities)

        events = (
            contribution_events
            + periodic_flow_events
            + pending_flow_events
            + maturity_events
        )
        events.sort(key=lambda e: (e.date, e.type.value, e.name))

        return MoneyEvents(events=events)

    def _build_contribution_events(
        self, contributions: Iterable[AutoContributions], query: MoneyEventQuery
    ) -> list[MoneyEvent]:
        events: list[MoneyEvent] = []
        for contrib in contributions:
            for periodic in contrib.periodic:
                occurrences = self._iterate_contribution_dates(periodic, query)
                for occurrence_date in occurrences:
                    events.append(
                        MoneyEvent(
                            id=periodic.id,
                            name=periodic.alias
                            or periodic.target_name
                            or periodic.target,
                            amount=periodic.amount,
                            currency=periodic.currency,
                            date=occurrence_date,
                            type=MoneyEventType.CONTRIBUTION,
                            frequency=self._to_money_event_frequency(
                                periodic.frequency.value
                            ),
                            details=PeriodicContributionDetails(
                                target_type=periodic.target_type,
                                target_subtype=periodic.target_subtype,
                                target=periodic.target,
                                target_name=periodic.target_name,
                            ),
                        )
                    )
        return events

    def _build_periodic_flow_events(
        self, flows: list[PeriodicFlow], query: MoneyEventQuery
    ) -> list[MoneyEvent]:
        events: list[MoneyEvent] = []
        for flow in flows:
            occurrences = self._iterate_periodic_flow_dates(flow, query)
            for occurrence_date in occurrences:
                events.append(
                    MoneyEvent(
                        id=flow.id,
                        name=flow.name,
                        amount=self._normalize_flow_amount(flow.amount, flow.flow_type),
                        currency=flow.currency,
                        date=occurrence_date,
                        type=MoneyEventType.PERIODIC_FLOW,
                        frequency=self._to_money_event_frequency(flow.frequency.value),
                        icon=flow.icon,
                    )
                )
        return events

    def _build_pending_flow_events(
        self, flows: list[PendingFlow], query: MoneyEventQuery
    ) -> list[MoneyEvent]:
        events: list[MoneyEvent] = []
        for flow in flows:
            if not flow.enabled:
                continue
            if flow.date and query.from_date <= flow.date <= query.to_date:
                events.append(
                    MoneyEvent(
                        id=flow.id,
                        name=flow.name,
                        amount=self._normalize_flow_amount(flow.amount, flow.flow_type),
                        currency=flow.currency,
                        date=flow.date,
                        type=MoneyEventType.PENDING_FLOW,
                        icon=flow.icon,
                    )
                )
        return events

    def _to_money_event_frequency(self, value: str) -> MoneyEventFrequency | None:
        normalized_value = "EVERY_TWO_MONTHS" if value == "BIMONTHLY" else value
        try:
            return MoneyEventFrequency(normalized_value)
        except ValueError:
            return None

    def _build_maturity_events(
        self, query: MoneyEventQuery, excluded_entities: list[UUID]
    ) -> list[MoneyEvent]:
        position_query = PositionQueryRequest(
            excluded_entities=excluded_entities or None,
            products=[
                ProductType.REAL_ESTATE_CF,
                ProductType.FACTORING,
                ProductType.DEPOSIT,
            ],
        )
        positions = self._position_port.get_last_grouped_by_entity(position_query)
        today = date.today()
        events: list[MoneyEvent] = []
        for position in positions.values():
            real_estate = position.products.get(ProductType.REAL_ESTATE_CF)
            if isinstance(real_estate, RealEstateCFInvestments):
                events.extend(
                    self._build_real_estate_cf_events(real_estate, query, today)
                )
            factoring = position.products.get(ProductType.FACTORING)
            if isinstance(factoring, FactoringInvestments):
                events.extend(self._build_factoring_events(factoring, query, today))
            deposits = position.products.get(ProductType.DEPOSIT)
            if isinstance(deposits, Deposits):
                events.extend(self._build_deposit_events(deposits, query, today))
        return events

    def _build_real_estate_cf_events(
        self, investments: RealEstateCFInvestments, query: MoneyEventQuery, today: date
    ) -> list[MoneyEvent]:
        events: list[MoneyEvent] = []
        for detail in investments.entries:
            event_date = self._resolve_real_estate_cf_maturity(detail, today)
            if not event_date:
                continue
            if not (query.from_date <= event_date <= query.to_date):
                continue
            if detail.profitability is None:
                continue
            events.append(
                MoneyEvent(
                    id=detail.id,
                    name=detail.name,
                    amount=round(detail.amount * detail.profitability, 2),
                    currency=detail.currency,
                    date=event_date,
                    type=MoneyEventType.MATURITY,
                    product_type=ProductType.REAL_ESTATE_CF,
                )
            )
        return events

    def _resolve_real_estate_cf_maturity(
        self, detail: RealEstateCFDetail, today: date
    ) -> date | None:
        maturity = detail.maturity
        if maturity and maturity >= today:
            return maturity
        extended = detail.extended_maturity
        if maturity and extended and maturity < today <= extended:
            return extended
        return None

    def _build_factoring_events(
        self, investments: FactoringInvestments, query: MoneyEventQuery, today: date
    ) -> list[MoneyEvent]:
        events: list[MoneyEvent] = []
        for detail in investments.entries:
            maturity = detail.maturity
            if not maturity or maturity < today:
                continue
            if not (query.from_date <= maturity <= query.to_date):
                continue
            if detail.profitability is None:
                continue
            events.append(
                MoneyEvent(
                    id=detail.id,
                    name=detail.name,
                    amount=round(detail.amount * detail.profitability, 2),
                    currency=detail.currency,
                    date=maturity,
                    type=MoneyEventType.MATURITY,
                    product_type=ProductType.FACTORING,
                )
            )
        return events

    def _build_deposit_events(
        self, deposits: Deposits, query: MoneyEventQuery, today: date
    ) -> list[MoneyEvent]:
        events: list[MoneyEvent] = []
        for detail in deposits.entries:
            maturity = detail.maturity
            if not maturity or maturity < today:
                continue
            if not (query.from_date <= maturity <= query.to_date):
                continue
            if detail.expected_interests is None:
                continue
            events.append(
                MoneyEvent(
                    id=detail.id,
                    name=detail.name,
                    amount=detail.expected_interests,
                    currency=detail.currency,
                    date=maturity,
                    type=MoneyEventType.MATURITY,
                    product_type=ProductType.DEPOSIT,
                )
            )
        return events

    def _normalize_flow_amount(self, amount: Dezimal, flow_type: FlowType) -> Dezimal:
        if flow_type == FlowType.EXPENSE:
            return amount * Dezimal(-1)
        return amount

    def _iterate_contribution_dates(
        self, periodic, query: MoneyEventQuery
    ) -> list[date]:
        occurrences: list[date] = []
        next_date = periodic.next_date
        if not next_date:
            return occurrences
        while next_date and next_date <= query.to_date:
            if next_date >= query.from_date:
                occurrences.append(next_date)
            next_date = self._advance_contribution_date(periodic, next_date)
            if periodic.until and next_date and next_date > periodic.until:
                break
        return occurrences

    def _advance_contribution_date(self, periodic, current: date) -> date | None:
        delta = self._contribution_delta(periodic.frequency.value)
        if delta:
            return current + delta
        if periodic.frequency.value in ("WEEKLY", "BIWEEKLY"):
            weeks = 2 if periodic.frequency.value == "BIWEEKLY" else 1
            return current + timedelta(weeks=weeks)
        return None

    def _contribution_delta(self, frequency: str) -> relativedelta | None:
        try:
            freq_enum = ContributionFrequency(frequency)
        except ValueError:
            return None
        return _contrib_freq_delta_map.get(freq_enum)

    def _iterate_periodic_flow_dates(
        self, flow: PeriodicFlow, query: MoneyEventQuery
    ) -> list[date]:
        occurrences: list[date] = []
        next_date = flow.next_date
        if not next_date:
            return occurrences
        while next_date and next_date <= query.to_date:
            if next_date >= query.from_date:
                occurrences.append(next_date)
            next_date = self._advance_periodic_flow_date(flow, next_date)
            if flow.until and next_date and next_date > flow.until:
                break
        return occurrences

    def _advance_periodic_flow_date(
        self, flow: PeriodicFlow, current: date
    ) -> date | None:
        delta = self._flow_delta(flow.frequency.value)
        if delta:
            return current + delta
        if flow.frequency.value == FlowFrequency.WEEKLY.value:
            return current + timedelta(weeks=1)
        if flow.frequency.value == FlowFrequency.DAILY.value:
            return current + timedelta(days=1)
        return None

    def _flow_delta(self, frequency: str) -> relativedelta | None:
        try:
            freq_enum = FlowFrequency(frequency)
        except ValueError:
            return None
        return frequency_delta_map.get(freq_enum)
