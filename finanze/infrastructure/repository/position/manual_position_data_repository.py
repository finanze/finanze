from datetime import date
from uuid import UUID

from application.ports.manual_position_data_port import ManualPositionDataPort
from domain.dezimal import Dezimal
from domain.global_position import ManualEntryData, ManualPositionData, ProductType
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.position.queries import ManualPositionDataQueries


class ManualPositionDataSQLRepository(ManualPositionDataPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    async def save(self, entries: list[ManualPositionData]):
        valid_entries = [e for e in entries if e is not None]
        if not valid_entries:
            return
        async with self._db_client.tx() as cursor:
            for entry in valid_entries:
                track_ticker = bool(entry.data and entry.data.tracker_key)
                track_loan = bool(entry.data and entry.data.track)
                await cursor.execute(
                    ManualPositionDataQueries.INSERT,
                    (
                        str(entry.entry_id),
                        str(entry.global_position_id),
                        entry.product_type.value,
                        track_ticker,
                        entry.data.tracker_key if entry.data else None,
                        track_loan,
                        str(entry.data.tracking_ref_outstanding)
                        if entry.data and entry.data.tracking_ref_outstanding
                        else None,
                        entry.data.tracking_ref_date.isoformat()
                        if entry.data and entry.data.tracking_ref_date
                        else None,
                    ),
                )

    async def get_trackable(self) -> list[ManualPositionData]:
        result: list[ManualPositionData] = []
        async with self._db_client.read() as cursor:
            await cursor.execute(ManualPositionDataQueries.GET_TRACKABLE)
            rows = await cursor.fetchall()
            for row in rows:
                result.append(
                    ManualPositionData(
                        entry_id=UUID(row["entry_id"]),
                        global_position_id=UUID(row["global_position_id"]),
                        product_type=ProductType(row["product_type"]),
                        data=ManualEntryData(tracker_key=row["tracker_key"]),
                    )
                )
        return result

    async def get_trackable_loans(self) -> list[ManualPositionData]:
        result: list[ManualPositionData] = []
        async with self._db_client.read() as cursor:
            await cursor.execute(ManualPositionDataQueries.GET_TRACKABLE_LOANS)
            rows = await cursor.fetchall()
            for row in rows:
                result.append(
                    ManualPositionData(
                        entry_id=UUID(row["entry_id"]),
                        global_position_id=UUID(row["global_position_id"]),
                        product_type=ProductType(row["product_type"]),
                        data=ManualEntryData(
                            track=True,
                            tracking_ref_outstanding=(
                                Dezimal(row["tracking_ref_outstanding"])
                                if row["tracking_ref_outstanding"]
                                else None
                            ),
                            tracking_ref_date=(
                                date.fromisoformat(row["tracking_ref_date"])
                                if row["tracking_ref_date"]
                                else None
                            ),
                        ),
                    )
                )
        return result

    async def update_tracking_ref(
        self, entry_id: UUID, ref_outstanding: Dezimal, ref_date: date
    ):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                ManualPositionDataQueries.UPDATE_TRACKING_REF,
                (str(ref_outstanding), ref_date.isoformat(), str(entry_id)),
            )

    async def delete_by_position_id(self, global_position_id: UUID):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                ManualPositionDataQueries.DELETE_BY_POSITION_ID,
                (str(global_position_id),),
            )

    async def delete_by_position_id_and_type(
        self, global_position_id: UUID, product_type: ProductType
    ):
        async with self._db_client.tx() as cursor:
            await cursor.execute(
                ManualPositionDataQueries.DELETE_BY_POSITION_ID_AND_TYPE,
                (str(global_position_id), product_type.value),
            )
