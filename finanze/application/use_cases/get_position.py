from application.ports.position_port import PositionPort
from domain.global_position import EntitiesPosition, PositionQueryRequest
from domain.use_cases.get_position import GetPosition


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

        return EntitiesPosition(global_position_by_entity)
