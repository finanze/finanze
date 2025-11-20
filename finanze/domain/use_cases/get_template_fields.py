import abc

from domain.entity import Feature
from domain.template_fields import FieldGroup


class GetTemplateFields(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self) -> dict[Feature, list[FieldGroup]]:
        raise NotImplementedError
