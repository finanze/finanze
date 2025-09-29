from datetime import datetime
from uuid import uuid4

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.entity_port import EntityPort
from application.ports.position_port import PositionPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from dateutil.tz import tzlocal
from domain.entity import Feature
from domain.exception.exceptions import EntityNotFound
from domain.global_position import GlobalPosition, UpdatePositionRequest
from domain.use_cases.update_position import UpdatePosition
from domain.virtual_fetch import VirtualDataImport, VirtualDataSource


class UpdatePositionImpl(UpdatePosition, AtomicUCMixin):
    def __init__(
        self,
        entity_port: EntityPort,
        position_port: PositionPort,
        virtual_import_registry: VirtualImportRegistry,
        transaction_handler_port: TransactionHandlerPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)
        self._entity_port = entity_port
        self._position_port = position_port
        self._virtual_import_registry = virtual_import_registry

    async def execute(self, request: UpdatePositionRequest):
        entity = self._entity_port.get_by_id(request.entity_id)
        if entity is None:
            raise EntityNotFound(request.entity_id)

        now = datetime.now(tzlocal())

        last_manual_imports = self._virtual_import_registry.get_last_import_records(
            source=VirtualDataSource.MANUAL
        )

        prior_position_entry = None
        for entry in last_manual_imports:
            if (
                entry.feature == Feature.POSITION
                and entry.entity_id == request.entity_id
            ):
                prior_position_entry = entry
                break

        prior_position = None
        if prior_position_entry:
            prior_position = self._position_port.get_by_id(
                prior_position_entry.global_position_id
            )

        if prior_position is None:
            base_position = GlobalPosition(
                id=uuid4(), entity=entity, date=now, products={}, is_real=False
            )
        else:
            base_position = GlobalPosition(
                id=uuid4(),
                entity=prior_position.entity,
                date=now,
                products=dict(prior_position.products),
                is_real=False,
            )

        for product_type, product_value in request.products.items():
            base_position.products[product_type] = product_value

        for product_type, product_value in base_position.products.items():
            if product_value and hasattr(product_value, "entries"):
                for entry in product_value.entries:
                    entry.id = uuid4()

        today = now.date()
        is_same_day = (
            last_manual_imports and last_manual_imports[0].date.date() == today
        )

        if is_same_day:
            import_id = last_manual_imports[0].import_id

            self._virtual_import_registry.delete_by_import_feature_and_entity(
                import_id, Feature.POSITION, request.entity_id
            )
            if prior_position_entry:
                self._position_port.delete_by_id(
                    prior_position_entry.global_position_id
                )

            self._position_port.save(base_position)

            new_entries = [
                VirtualDataImport(
                    import_id=import_id,
                    global_position_id=base_position.id,
                    source=VirtualDataSource.MANUAL,
                    date=now,
                    feature=Feature.POSITION,
                    entity_id=request.entity_id,
                )
            ]
            self._virtual_import_registry.insert(new_entries)
            return

        import_id = uuid4()
        self._position_port.save(base_position)

        cloned_entries = []
        for entry in last_manual_imports:
            if (
                entry.feature == Feature.POSITION
                and entry.entity_id == request.entity_id
            ):
                continue

            cloned_entries.append(
                VirtualDataImport(
                    import_id=import_id,
                    global_position_id=entry.global_position_id,
                    source=entry.source,
                    date=now,
                    feature=entry.feature,
                    entity_id=entry.entity_id,
                )
            )

        cloned_entries.append(
            VirtualDataImport(
                import_id=import_id,
                global_position_id=base_position.id,
                source=VirtualDataSource.MANUAL,
                date=now,
                feature=Feature.POSITION,
                entity_id=request.entity_id,
            )
        )

        self._virtual_import_registry.insert(cloned_entries)
