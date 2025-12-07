import abc

from domain.template import Template
from domain.template_type import TemplateType


class GetTemplates(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, template_type: TemplateType) -> list[Template]:
        raise NotImplementedError
