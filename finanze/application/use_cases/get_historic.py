from application.ports.entity_port import EntityPort
from application.ports.historic_port import HistoricPort
from domain.historic import Historic, HistoricQueryRequest
from domain.use_cases.get_historic import GetHistoric


class GetHistoricImpl(GetHistoric):
    def __init__(self, historic_port: HistoricPort, entity_port: EntityPort):
        self._historic_port = historic_port
        self._entity_port = entity_port

    async def execute(self, query: HistoricQueryRequest) -> Historic:
        excluded_entities = [
            e.id for e in await self._entity_port.get_disabled_entities()
        ]

        query.excluded_entities = excluded_entities

        return await self._historic_port.get_by_filters(query, fetch_related_txs=True)
