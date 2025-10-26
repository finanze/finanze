from datetime import date

from application.ports.position_port import PositionPort
from dateutil.relativedelta import relativedelta
from domain.global_position import EntitiesPosition, PositionQueryRequest, ProductType
from domain.use_cases.get_position import GetPosition


def _calculate_next_loan_payment_date(loan):
    today = date.today()

    if loan.maturity <= today:
        return None

    anchor = loan.creation

    if anchor > today:
        candidate = anchor
    else:
        candidate = anchor
        while candidate <= today:
            candidate = candidate + relativedelta(months=1)

    if candidate > loan.maturity:
        return None

    return candidate


def _enrich_loans(position):
    if ProductType.LOAN not in position.products:
        return

    loans = position.products[ProductType.LOAN]
    if not loans or not loans.entries:
        return

    for loan in loans.entries:
        if loan.next_payment_date is None:
            loan.next_payment_date = _calculate_next_loan_payment_date(loan)


def _enrich_data(data: dict):
    for entity_id, position in data.items():
        if position is None:
            continue
        _enrich_loans(position)


class GetPositionImpl(GetPosition):
    def __init__(self, position_port: PositionPort):
        self._position_port = position_port

    def execute(self, query: PositionQueryRequest) -> EntitiesPosition:
        query = PositionQueryRequest(
            entities=query.entities, excluded_entities=query.excluded_entities
        )
        global_position_by_entity = self._position_port.get_last_grouped_by_entity(
            query
        )

        global_position_by_entity = {
            str(entity.id): position
            for entity, position in global_position_by_entity.items()
        }

        _enrich_data(global_position_by_entity)

        return EntitiesPosition(global_position_by_entity)
