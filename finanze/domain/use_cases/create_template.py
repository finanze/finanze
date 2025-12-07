import abc
from domain.template import Template


class CreateTemplate(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, template: Template):
        raise NotImplementedError
