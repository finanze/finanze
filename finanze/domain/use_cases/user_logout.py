import abc


class UserLogout(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def execute(self):
        raise NotImplementedError
