import abc


class ConfigPort(metaclass=abc.ABCMeta):

    def load(self) -> dict:
        raise NotImplementedError
