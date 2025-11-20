import abc

from domain.export import TemplatedDataProcessorParams


class TemplateProcessorPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def process(
        self, data: list, params: TemplatedDataProcessorParams
    ) -> list[list[str]]:
        raise NotImplementedError
