from datetime import date, timedelta

from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.entity_port import EntityPort
from dateutil.relativedelta import relativedelta
from domain.auto_contributions import (
    AutoContributions,
    ContributionFrequency,
    ContributionQueryRequest,
    EntityContributions,
    PeriodicContribution,
)
from domain.use_cases.get_contributions import GetContributions

_contrib_freq_delta_map = {
    ContributionFrequency.MONTHLY: relativedelta(months=1),
    ContributionFrequency.BIMONTHLY: relativedelta(months=2),
    ContributionFrequency.EVERY_FOUR_MONTHS: relativedelta(months=4),
    ContributionFrequency.QUARTERLY: relativedelta(months=3),
    ContributionFrequency.SEMIANNUAL: relativedelta(months=6),
    ContributionFrequency.YEARLY: relativedelta(years=1),
}


def _next_contribution_date(pc: PeriodicContribution) -> date | None:
    if not pc.active:
        return None

    today = date.today()
    since_date = pc.since
    next_date: date | None = None

    if since_date > today:
        return since_date

    if pc.frequency in (ContributionFrequency.WEEKLY, ContributionFrequency.BIWEEKLY):
        weeks_interval = 2 if pc.frequency == ContributionFrequency.BIWEEKLY else 1
        days_since = (today - since_date).days
        periods_passed = days_since // (weeks_interval * 7)
        next_date = since_date + timedelta(weeks=(periods_passed + 1) * weeks_interval)
        if next_date <= today:
            next_date = since_date + timedelta(
                weeks=(periods_passed + 2) * weeks_interval
            )

    elif pc.frequency in _contrib_freq_delta_map:
        delta = _contrib_freq_delta_map[pc.frequency]
        next_date = since_date
        while next_date <= today:
            next_date = next_date + delta

    if next_date and pc.until and next_date > pc.until:
        return None

    return next_date


class GetContributionsImpl(GetContributions):
    def __init__(
        self, auto_contributions_port: AutoContributionsPort, entity_port: EntityPort
    ):
        self._auto_contributions_port = auto_contributions_port
        self._entity_port = entity_port

    def execute(self, query: ContributionQueryRequest) -> EntityContributions:
        excluded_entities = [e.id for e in self._entity_port.get_disabled_entities()]

        query.excluded_entities = excluded_entities
        data = self._auto_contributions_port.get_all_grouped_by_entity(query)

        contributions: dict[str, AutoContributions] = {}
        for entity, contrib in data.items():
            updated_periodic: list[PeriodicContribution] = []
            for pc in contrib.periodic:
                updated_periodic.append(
                    PeriodicContribution(
                        id=pc.id,
                        alias=pc.alias,
                        target=pc.target,
                        target_name=pc.target_name,
                        target_type=pc.target_type,
                        target_subtype=pc.target_subtype,
                        amount=pc.amount,
                        currency=pc.currency,
                        since=pc.since,
                        until=pc.until,
                        frequency=pc.frequency,
                        active=pc.active,
                        source=pc.source,
                        next_date=_next_contribution_date(pc),
                    )
                )
            contributions[str(entity.id)] = AutoContributions(periodic=updated_periodic)

        return EntityContributions(contributions)
