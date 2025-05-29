from application.ports.position_port import PositionPort
from domain.global_position import EntitiesPosition, PositionQueryRequest
from domain.use_cases.get_position import GetPosition


class GetPositionImpl(GetPosition):

    def __init__(self, position_port: PositionPort):
        self._position_port = position_port

    def execute(self, query: PositionQueryRequest) -> EntitiesPosition:
        query_real = PositionQueryRequest(entities=query.entities, excluded_entities=query.excluded_entities, real=True)
        real_global_position_by_entity = self._position_port.get_last_grouped_by_entity(query_real)

        query_manual = PositionQueryRequest(entities=query.entities, excluded_entities=query.excluded_entities,
                                            real=False)
        manual_global_position_by_entity = self._position_port.get_last_grouped_by_entity(query_manual)

        global_position_by_entity = {}
        for entity, position in real_global_position_by_entity.items():
            if entity in manual_global_position_by_entity:
                global_position_by_entity[entity] += manual_global_position_by_entity[entity]
                del manual_global_position_by_entity[entity]
            else:
                global_position_by_entity[entity] = position

        for entity, position in manual_global_position_by_entity.items():
            global_position_by_entity[entity] = position

        global_position_by_entity = {str(entity.id): position for entity, position in global_position_by_entity.items()}

        return EntitiesPosition(global_position_by_entity)
