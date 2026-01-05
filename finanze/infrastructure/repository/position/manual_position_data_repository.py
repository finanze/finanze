from uuid import UUID

from application.ports.manual_position_data_port import ManualPositionDataPort
from domain.global_position import ManualEntryData, ManualPositionData, ProductType
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.position.queries import ManualPositionDataQueries


class ManualPositionDataSQLRepository(ManualPositionDataPort):
    def __init__(self, client: DBClient):
        self._db_client = client

    def save(self, entries: list[ManualPositionData]):
        valid_entries = [e for e in entries if e is not None]
        if not valid_entries:
            return
        with self._db_client.tx() as cursor:
            for entry in valid_entries:
                track_ticker = bool(entry.data and entry.data.tracker_key)
                cursor.execute(
                    ManualPositionDataQueries.INSERT,
                    (
                        str(entry.entry_id),
                        str(entry.global_position_id),
                        entry.product_type.value,
                        track_ticker,
                        entry.data.tracker_key if entry.data else None,
                    ),
                )

    def get_trackable(self) -> list[ManualPositionData]:
        result: list[ManualPositionData] = []
        with self._db_client.read() as cursor:
            cursor.execute(ManualPositionDataQueries.GET_TRACKABLE)
            rows = cursor.fetchall()
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

    def delete_by_position_id_and_type(
        self, global_position_id: UUID, product_type: ProductType
    ):
        with self._db_client.tx() as cursor:
            cursor.execute(
                ManualPositionDataQueries.DELETE_BY_POSITION_ID_AND_TYPE,
                (str(global_position_id), product_type.value),
            )
