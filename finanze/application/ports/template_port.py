import abc
from uuid import UUID

from domain.template import Template
from domain.template_type import TemplateType


class TemplatePort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, template: Template):
        raise NotImplementedError

    @abc.abstractmethod
    def update(self, template: Template):
        raise NotImplementedError

    @abc.abstractmethod
    def delete(self, template_id: UUID):
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_id(self, template_id: UUID) -> Template | None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_type(self, template_type: TemplateType) -> list[Template]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_by_name_and_type(
        self, name: str, template_type: TemplateType
    ) -> Template | None:
        raise NotImplementedError
