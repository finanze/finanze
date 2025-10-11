from application.ports.historic_port import HistoricPort
from domain.historic import Historic, HistoricQueryRequest
from domain.use_cases.get_historic import GetHistoric


class GetHistoricImpl(GetHistoric):
    def __init__(self, historic_port: HistoricPort):
        self._historic_port = historic_port

    def execute(self, query: HistoricQueryRequest) -> Historic:
        if not any([query.entities, query.excluded_entities, query.product_types]):
            return self._historic_port.get_all(fetch_related_txs=True)

        return self._historic_port.get_by_filters(query, fetch_related_txs=True)
