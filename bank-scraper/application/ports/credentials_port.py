import abc

from domain.financial_entity import Entity


class CredentialsPort(metaclass=abc.ABCMeta):

    def get(self, entity: Entity) -> tuple:
        raise NotImplementedError
