import abc
from typing import Optional
from uuid import UUID

from domain.entity import Feature
from domain.virtual_data import VirtualDataImport, VirtualDataSource


class VirtualImportRegistry(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def insert(self, entries: list[VirtualDataImport]):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_last_import_records(
        self, source: Optional[VirtualDataSource] = None
    ) -> list[VirtualDataImport]:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_by_import_and_feature(self, import_id: UUID, feature: Feature):
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_by_import_feature_and_entity(
        self, import_id: UUID, feature: Feature, entity_id: UUID
    ):
        raise NotImplementedError
