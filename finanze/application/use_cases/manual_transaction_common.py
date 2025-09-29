from datetime import datetime
from uuid import UUID, uuid4

from application.ports.virtual_import_registry import VirtualImportRegistry
from dateutil.tz import tzlocal
from domain.entity import Feature
from domain.virtual_fetch import VirtualDataImport, VirtualDataSource


class ManualTransactionVirtualImportHelper:
    def __init__(self, virtual_import_registry: VirtualImportRegistry):
        self._virtual_import_registry = virtual_import_registry

    def refresh(self, entity_id: UUID, has_transactions: bool):
        now = datetime.now(tzlocal())
        today = now.date()
        cloned = []
        last_manual_imports = self._virtual_import_registry.get_last_import_records(
            source=VirtualDataSource.MANUAL
        )
        is_same_day = (
            last_manual_imports and last_manual_imports[0].date.date() == today
        )

        if is_same_day:
            import_id = last_manual_imports[0].import_id

            self._virtual_import_registry.delete_by_import_feature_and_entity(
                import_id, Feature.TRANSACTIONS, entity_id
            )

        else:
            import_id = uuid4()
            for entry in last_manual_imports:
                if (
                    entry.feature == Feature.TRANSACTIONS
                    and entry.entity_id == entity_id
                ):
                    continue

                cloned.append(
                    VirtualDataImport(
                        import_id=import_id,
                        global_position_id=entry.global_position_id,
                        source=entry.source,
                        date=now,
                        feature=entry.feature,
                        entity_id=entry.entity_id,
                    )
                )

        if has_transactions:
            cloned.append(
                VirtualDataImport(
                    import_id=import_id,
                    global_position_id=None,
                    source=VirtualDataSource.MANUAL,
                    date=now,
                    feature=Feature.TRANSACTIONS,
                    entity_id=entity_id,
                )
            )

        if cloned:
            self._virtual_import_registry.insert(cloned)
