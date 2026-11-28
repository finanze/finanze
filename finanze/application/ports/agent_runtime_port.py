import abc


class AgentRuntimePort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def release_all(self):
        raise NotImplementedError
