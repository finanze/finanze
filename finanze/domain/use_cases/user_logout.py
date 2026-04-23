import abc


class UserLogout(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(self):
        raise NotImplementedError
