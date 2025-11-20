import abc
from uuid import UUID


class DeleteTemplate(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, template_id: UUID):
        raise NotImplementedError
