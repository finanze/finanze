import abc


class UpdateSheets(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self):
        raise NotImplementedError
