from datetime import datetime
from uuid import UUID, uuid4

from application.mixins.atomic_use_case import AtomicUCMixin
from application.ports.auto_contributions_port import AutoContributionsPort
from application.ports.entity_port import EntityPort
from application.ports.transaction_handler_port import TransactionHandlerPort
from application.ports.virtual_import_registry import VirtualImportRegistry
from dateutil.tz import tzlocal
from domain.auto_contributions import (
    AutoContributions,
    ManualPeriodicContribution,
    PeriodicContribution,
)
from domain.entity import Feature
from domain.exception.exceptions import EntityNotFound
from domain.fetch_record import DataSource
from domain.use_cases.update_contributions import UpdateContributions
from domain.virtual_data import VirtualDataImport, VirtualDataSource


def _map_manual_contribution(
    manual_contribution: ManualPeriodicContribution,
) -> PeriodicContribution:
    return PeriodicContribution(
        id=uuid4(),
        target=manual_contribution.target,
        target_type=manual_contribution.target_type,
        target_subtype=manual_contribution.target_subtype,
        alias=manual_contribution.name,
        target_name=manual_contribution.target_name,
        amount=manual_contribution.amount,
        currency=manual_contribution.currency,
        since=manual_contribution.since,
        until=manual_contribution.until,
        frequency=manual_contribution.frequency,
        active=True,
        source=DataSource.MANUAL,
    )


class UpdateContributionsImpl(UpdateContributions, AtomicUCMixin):
    def __init__(
        self,
        entity_port: EntityPort,
        auto_contributions_port: AutoContributionsPort,
        virtual_import_registry: VirtualImportRegistry,
        transaction_handler_port: TransactionHandlerPort,
    ):
        AtomicUCMixin.__init__(self, transaction_handler_port)
        self._entity_port = entity_port
        self._auto_contributions_port = auto_contributions_port
        self._virtual_import_registry = virtual_import_registry

    async def execute(self, contributions: list[ManualPeriodicContribution]):
        self._auto_contributions_port.delete_by_source(DataSource.MANUAL)

        contributions_by_entity: dict[UUID, AutoContributions] = {}
        for c in contributions:
            if self._entity_port.get_by_id(c.entity_id) is None:
                raise EntityNotFound(c.entity_id)

            mapped_contribution = _map_manual_contribution(c)
            if contributions_by_entity.get(c.entity_id) is None:
                contributions_by_entity[c.entity_id] = AutoContributions(periodic=[])
            contributions_by_entity[c.entity_id].periodic.append(mapped_contribution)

        for entity_id, auto_contributions in contributions_by_entity.items():
            self._auto_contributions_port.save(
                entity_id, auto_contributions, DataSource.MANUAL
            )

        import_id = None
        import_date = datetime.now(tzlocal())
        last_manual_imports = self._virtual_import_registry.get_last_import_records(
            source=VirtualDataSource.MANUAL
        )
        today = datetime.now(tzlocal()).date()

        if (
            last_manual_imports
            and (last_import_entry := last_manual_imports[0]).date.date() == today
        ):
            import_id = last_import_entry.import_id

            self._virtual_import_registry.delete_by_import_and_feature(
                import_id, Feature.AUTO_CONTRIBUTIONS
            )

        else:
            import_id = uuid4()

            if last_manual_imports:
                new_entries = []
                for entry in last_manual_imports:
                    if entry.feature in (Feature.TRANSACTIONS, Feature.POSITION):
                        new_entry = VirtualDataImport(
                            import_id=import_id,
                            global_position_id=entry.global_position_id,
                            source=entry.source,
                            date=import_date,
                            feature=entry.feature,
                            entity_id=entry.entity_id,
                        )
                        new_entries.append(new_entry)
                self._virtual_import_registry.insert(new_entries)

        new_contribution_entries = []
        for entity_id in contributions_by_entity.keys():
            new_entry = VirtualDataImport(
                import_id=import_id,
                global_position_id=None,
                source=VirtualDataSource.MANUAL,
                date=import_date,
                feature=Feature.AUTO_CONTRIBUTIONS,
                entity_id=entity_id,
            )
            new_contribution_entries.append(new_entry)

        self._virtual_import_registry.insert(new_contribution_entries)
