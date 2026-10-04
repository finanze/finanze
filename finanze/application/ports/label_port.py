import abc
from typing import Optional
from uuid import UUID

from domain.labeling import Label


class LabelPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_all(self) -> list[Label]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_by_id(self, label_id: UUID) -> Optional[Label]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_usage(self) -> dict[UUID, int]:
        raise NotImplementedError

    @abc.abstractmethod
    async def save(self, label: Label) -> Label:
        raise NotImplementedError

    @abc.abstractmethod
    async def update(self, label: Label):
        raise NotImplementedError

    @abc.abstractmethod
    async def delete(self, label_id: UUID):
        raise NotImplementedError
