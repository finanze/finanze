import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from dateutil.tz import tzlocal

from domain.dezimal import Dezimal
from domain.entity import Entity, EntityOrigin, EntityType
from domain.fetch_record import DataSource
from domain.global_position import (
    Account,
    AccountType,
    Accounts,
    GlobalPosition,
    PositionQueryRequest,
    ProductType,
)
from infrastructure.repository.position.position_repository import (
    PositionSQLRepository,
)

ENTITY_A = Entity(
    id=uuid.UUID("a0000000-0000-0000-0000-000000000001"),
    name="Entity A",
    natural_id=None,
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.NATIVE,
    icon_url=None,
)

ENTITY_B = Entity(
    id=uuid.UUID("b0000000-0000-0000-0000-000000000001"),
    name="Entity B",
    natural_id=None,
    type=EntityType.FINANCIAL_INSTITUTION,
    origin=EntityOrigin.MANUAL,
    icon_url=None,
)


def _make_position(entity, source=DataSource.REAL, total="1000"):
    return GlobalPosition(
        id=uuid.uuid4(),
        entity=entity,
        date=datetime.now(tzlocal()),
        products={
            ProductType.ACCOUNT: Accounts(
                [
                    Account(
                        id=uuid.uuid4(),
                        total=Dezimal(total),
                        currency="EUR",
                        type=AccountType.CHECKING,
                        source=source,
                    )
                ]
            )
        },
        source=source,
    )


def _make_repo(real_return=None, manual_return=None):
    db_client = MagicMock()
    repo = PositionSQLRepository(db_client)
    repo._get_real_grouped_by_entity = AsyncMock(return_value=real_return or {})
    repo._get_non_real_grouped_by_entity = AsyncMock(return_value=manual_return or {})
    return repo


# ---------------------------------------------------------------------------
# get_last_by_entity_broken_down
# ---------------------------------------------------------------------------


class TestGetLastByEntityBrokenDown:
    @pytest.mark.asyncio
    async def test_empty_when_no_positions(self):
        repo = _make_repo()
        result = await repo.get_last_by_entity_broken_down()
        assert result == {}

    @pytest.mark.asyncio
    async def test_single_real_position(self):
        pos = _make_position(ENTITY_A, DataSource.REAL)
        repo = _make_repo(real_return={ENTITY_A: [pos]})

        result = await repo.get_last_by_entity_broken_down()
        assert ENTITY_A in result
        assert result[ENTITY_A] == [pos]

    @pytest.mark.asyncio
    async def test_single_manual_position(self):
        pos = _make_position(ENTITY_A, DataSource.MANUAL)
        repo = _make_repo(manual_return={ENTITY_A: [pos]})

        result = await repo.get_last_by_entity_broken_down()
        assert ENTITY_A in result
        assert result[ENTITY_A] == [pos]

    @pytest.mark.asyncio
    async def test_multiple_real_positions_same_entity(self):
        pos1 = _make_position(ENTITY_A, DataSource.REAL, "1000")
        pos2 = _make_position(ENTITY_A, DataSource.REAL, "2000")
        repo = _make_repo(real_return={ENTITY_A: [pos1, pos2]})

        result = await repo.get_last_by_entity_broken_down()
        assert len(result[ENTITY_A]) == 2
        assert pos1 in result[ENTITY_A]
        assert pos2 in result[ENTITY_A]

    @pytest.mark.asyncio
    async def test_multiple_manual_positions_same_entity(self):
        pos1 = _make_position(ENTITY_A, DataSource.MANUAL, "500")
        pos2 = _make_position(ENTITY_A, DataSource.MANUAL, "700")
        repo = _make_repo(manual_return={ENTITY_A: [pos1, pos2]})

        result = await repo.get_last_by_entity_broken_down()
        assert len(result[ENTITY_A]) == 2
        assert pos1 in result[ENTITY_A]
        assert pos2 in result[ENTITY_A]

    @pytest.mark.asyncio
    async def test_real_and_manual_same_entity_merged_into_list(self):
        real_pos = _make_position(ENTITY_A, DataSource.REAL, "1000")
        manual_pos = _make_position(ENTITY_A, DataSource.MANUAL, "500")
        repo = _make_repo(
            real_return={ENTITY_A: [real_pos]},
            manual_return={ENTITY_A: [manual_pos]},
        )

        result = await repo.get_last_by_entity_broken_down()
        assert len(result[ENTITY_A]) == 2
        assert real_pos in result[ENTITY_A]
        assert manual_pos in result[ENTITY_A]

    @pytest.mark.asyncio
    async def test_multiple_real_and_multiple_manual_same_entity(self):
        real1 = _make_position(ENTITY_A, DataSource.REAL, "1000")
        real2 = _make_position(ENTITY_A, DataSource.REAL, "2000")
        manual1 = _make_position(ENTITY_A, DataSource.MANUAL, "300")
        manual2 = _make_position(ENTITY_A, DataSource.MANUAL, "400")
        repo = _make_repo(
            real_return={ENTITY_A: [real1, real2]},
            manual_return={ENTITY_A: [manual1, manual2]},
        )

        result = await repo.get_last_by_entity_broken_down()
        assert len(result[ENTITY_A]) == 4
        for pos in [real1, real2, manual1, manual2]:
            assert pos in result[ENTITY_A]

    @pytest.mark.asyncio
    async def test_different_entities_kept_separate(self):
        real_a = _make_position(ENTITY_A, DataSource.REAL, "1000")
        manual_b = _make_position(ENTITY_B, DataSource.MANUAL, "500")
        repo = _make_repo(
            real_return={ENTITY_A: [real_a]},
            manual_return={ENTITY_B: [manual_b]},
        )

        result = await repo.get_last_by_entity_broken_down()
        assert len(result) == 2
        assert result[ENTITY_A] == [real_a]
        assert result[ENTITY_B] == [manual_b]

    @pytest.mark.asyncio
    async def test_mixed_entities_some_shared_some_not(self):
        real_a = _make_position(ENTITY_A, DataSource.REAL, "1000")
        manual_a = _make_position(ENTITY_A, DataSource.MANUAL, "200")
        manual_b = _make_position(ENTITY_B, DataSource.MANUAL, "500")
        repo = _make_repo(
            real_return={ENTITY_A: [real_a]},
            manual_return={ENTITY_A: [manual_a], ENTITY_B: [manual_b]},
        )

        result = await repo.get_last_by_entity_broken_down()
        assert len(result) == 2
        assert len(result[ENTITY_A]) == 2
        assert real_a in result[ENTITY_A]
        assert manual_a in result[ENTITY_A]
        assert result[ENTITY_B] == [manual_b]

    @pytest.mark.asyncio
    async def test_real_filter_only_queries_real(self):
        repo = _make_repo()
        query = PositionQueryRequest(real=True)

        await repo.get_last_by_entity_broken_down(query)
        repo._get_real_grouped_by_entity.assert_awaited_once_with(query)
        repo._get_non_real_grouped_by_entity.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_real_filter_only_queries_manual(self):
        repo = _make_repo()
        query = PositionQueryRequest(real=False)

        await repo.get_last_by_entity_broken_down(query)
        repo._get_real_grouped_by_entity.assert_not_awaited()
        repo._get_non_real_grouped_by_entity.assert_awaited_once_with(query)

    @pytest.mark.asyncio
    async def test_no_query_fetches_both(self):
        repo = _make_repo()
        await repo.get_last_by_entity_broken_down()
        repo._get_real_grouped_by_entity.assert_awaited_once()
        repo._get_non_real_grouped_by_entity.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_real_none_filter_fetches_both(self):
        repo = _make_repo()
        query = PositionQueryRequest(real=None)
        await repo.get_last_by_entity_broken_down(query)
        repo._get_real_grouped_by_entity.assert_awaited_once()
        repo._get_non_real_grouped_by_entity.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_last_grouped_by_entity
# ---------------------------------------------------------------------------


class TestGetLastGroupedByEntity:
    @pytest.mark.asyncio
    async def test_empty_when_no_positions(self):
        repo = _make_repo()
        result = await repo.get_last_grouped_by_entity()
        assert result == {}

    @pytest.mark.asyncio
    async def test_single_real_position(self):
        pos = _make_position(ENTITY_A, DataSource.REAL)
        repo = _make_repo(real_return={ENTITY_A: [pos]})

        result = await repo.get_last_grouped_by_entity()
        assert ENTITY_A in result
        assert result[ENTITY_A] is pos

    @pytest.mark.asyncio
    async def test_single_manual_position(self):
        pos = _make_position(ENTITY_A, DataSource.MANUAL)
        repo = _make_repo(manual_return={ENTITY_A: [pos]})

        result = await repo.get_last_grouped_by_entity()
        assert ENTITY_A in result
        assert result[ENTITY_A] is pos

    @pytest.mark.asyncio
    async def test_real_only_entity_and_manual_only_entity(self):
        real_a = _make_position(ENTITY_A, DataSource.REAL, "1000")
        manual_b = _make_position(ENTITY_B, DataSource.MANUAL, "500")
        repo = _make_repo(
            real_return={ENTITY_A: [real_a]},
            manual_return={ENTITY_B: [manual_b]},
        )

        result = await repo.get_last_grouped_by_entity()
        assert len(result) == 2
        assert result[ENTITY_A] is real_a
        assert result[ENTITY_B] is manual_b

    @pytest.mark.asyncio
    async def test_real_and_manual_same_entity_are_combined(self):
        real_pos = _make_position(ENTITY_A, DataSource.REAL, "1000")
        manual_pos = _make_position(ENTITY_A, DataSource.MANUAL, "500")
        repo = _make_repo(
            real_return={ENTITY_A: [real_pos]},
            manual_return={ENTITY_A: [manual_pos]},
        )

        result = await repo.get_last_grouped_by_entity()
        assert ENTITY_A in result
        # _aggregate_positions returns the single item for single-element lists
        # then real + manual are combined via +
        combined = result[ENTITY_A]
        assert combined is not None

    @pytest.mark.asyncio
    async def test_manual_entity_not_in_real_still_included(self):
        real_a = _make_position(ENTITY_A, DataSource.REAL, "1000")
        manual_b = _make_position(ENTITY_B, DataSource.MANUAL, "500")
        repo = _make_repo(
            real_return={ENTITY_A: [real_a]},
            manual_return={ENTITY_B: [manual_b]},
        )

        result = await repo.get_last_grouped_by_entity()
        assert ENTITY_A in result
        assert ENTITY_B in result
        assert result[ENTITY_A] is real_a
        assert result[ENTITY_B] is manual_b

    @pytest.mark.asyncio
    async def test_manual_entity_overlapping_with_real_removed_from_manual_dict(self):
        real_pos = _make_position(ENTITY_A, DataSource.REAL, "1000")
        manual_pos_a = _make_position(ENTITY_A, DataSource.MANUAL, "200")
        manual_pos_b = _make_position(ENTITY_B, DataSource.MANUAL, "500")
        repo = _make_repo(
            real_return={ENTITY_A: [real_pos]},
            manual_return={ENTITY_A: [manual_pos_a], ENTITY_B: [manual_pos_b]},
        )

        result = await repo.get_last_grouped_by_entity()
        assert len(result) == 2
        # ENTITY_A had both real and manual — combined
        assert result[ENTITY_A] is not None
        # ENTITY_B was manual-only — still present
        assert result[ENTITY_B] is manual_pos_b

    @pytest.mark.asyncio
    async def test_real_filter_only_queries_real(self):
        repo = _make_repo()
        query = PositionQueryRequest(real=True)

        await repo.get_last_grouped_by_entity(query)
        repo._get_real_grouped_by_entity.assert_awaited_once_with(query)
        repo._get_non_real_grouped_by_entity.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_real_filter_only_queries_manual(self):
        repo = _make_repo()
        query = PositionQueryRequest(real=False)

        await repo.get_last_grouped_by_entity(query)
        repo._get_real_grouped_by_entity.assert_not_awaited()
        repo._get_non_real_grouped_by_entity.assert_awaited_once_with(query)

    @pytest.mark.asyncio
    async def test_no_query_fetches_both(self):
        repo = _make_repo()
        await repo.get_last_grouped_by_entity()
        repo._get_real_grouped_by_entity.assert_awaited_once()
        repo._get_non_real_grouped_by_entity.assert_awaited_once()
