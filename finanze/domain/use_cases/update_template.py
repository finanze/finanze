import abc
from domain.template import Template


class UpdateTemplate(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, template: Template):
        raise NotImplementedError
