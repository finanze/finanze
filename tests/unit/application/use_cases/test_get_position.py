from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from application.ports.entity_port import EntityPort
from application.ports.position_port import PositionPort
from application.use_cases.get_position import GetPositionImpl
from domain.entity import Entity, EntityOrigin, EntityType
from domain.global_position import PositionQueryRequest, ProductType


def _entity():
    return Entity(
        id=uuid4(),
        name="Disabled",
        natural_id=None,
        type=EntityType.FINANCIAL_INSTITUTION,
        origin=EntityOrigin.MANUAL,
        icon_url=None,
    )


class TestGetPositionQuery:
    @pytest.mark.asyncio
    async def test_forwards_filters_and_excludes_disabled_entities(self):
        position_port = AsyncMock(spec=PositionPort)
        position_port.get_last_by_entity_broken_down.return_value = {}
        entity_port = AsyncMock(spec=EntityPort)
        disabled = _entity()
        entity_port.get_disabled_entities.return_value = [disabled]
        entity_id = uuid4()

        await GetPositionImpl(position_port, entity_port).execute(
            PositionQueryRequest(
                entities=[entity_id],
                real=False,
                products=[ProductType.ACCOUNT],
            )
        )

        query = position_port.get_last_by_entity_broken_down.await_args.args[0]
        assert query.entities == [entity_id]
        assert query.excluded_entities == [disabled.id]
        assert query.real is False
        assert query.products == [ProductType.ACCOUNT]
