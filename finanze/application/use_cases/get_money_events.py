from typing import Iterable

from application.ports.entity_port import EntityPort
from domain.auto_contributions import AutoContributions, ContributionQueryRequest
from domain.earnings_expenses import PendingFlow, PeriodicFlow
from domain.money_event import (
    MoneyEvent,
    MoneyEventQuery,
    MoneyEvents,
    MoneyEventType,
    MoneyEventFrequency,
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
    ):
        self._get_contributions = get_contributions_uc
        self._get_periodic_flows = get_periodic_flows_uc
        self._get_pending_flows = get_pending_flows_uc
        self._entity_port = entity_port

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

        events = contribution_events + periodic_flow_events + pending_flow_events
        events.sort(key=lambda e: (e.date, e.type.value, e.name))

        return MoneyEvents(events=events)

    def _build_contribution_events(
        self, contributions: Iterable[AutoContributions], query: MoneyEventQuery
    ) -> list[MoneyEvent]:
        events: list[MoneyEvent] = []
        for contrib in contributions:
            for periodic in contrib.periodic:
                if not periodic.next_date:
                    continue
                if periodic.until and periodic.next_date > periodic.until:
                    continue
                if not (query.from_date <= periodic.next_date <= query.to_date):
                    continue
                events.append(
                    MoneyEvent(
                        id=periodic.id,
                        name=periodic.alias or periodic.target_name or periodic.target,
                        amount=periodic.amount,
                        currency=periodic.currency,
                        date=periodic.next_date,
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
            if flow.next_date and query.from_date <= flow.next_date <= query.to_date:
                events.append(
                    MoneyEvent(
                        id=flow.id,
                        name=flow.name,
                        amount=flow.amount,
                        currency=flow.currency,
                        date=flow.next_date,
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
                        amount=flow.amount,
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
