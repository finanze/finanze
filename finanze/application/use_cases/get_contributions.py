from application.ports.auto_contributions_port import AutoContributionsPort
from domain.auto_contributions import EntityContributions, ContributionQueryRequest
from domain.use_cases.get_contributions import GetContributions


class GetContributionsImpl(GetContributions):
    def __init__(self, auto_contributions_port: AutoContributionsPort):
        self._auto_contributions_port = auto_contributions_port

    def execute(self, query: ContributionQueryRequest) -> EntityContributions:
        data = self._auto_contributions_port.get_all_grouped_by_entity(query)
        contributions = {str(entity.id): contrib for entity, contrib in data.items()}

        return EntityContributions(contributions)
