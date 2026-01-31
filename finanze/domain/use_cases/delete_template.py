import abc
from uuid import UUID


class DeleteTemplate(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self, template_id: UUID):
        raise NotImplementedError
