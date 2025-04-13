import abc

from domain.financial_entity import FinancialEntity


class CredentialsPort(metaclass=abc.ABCMeta):

    def get(self, entity: FinancialEntity) -> tuple:
        raise NotImplementedError

    def get_available_entities(self) -> list[FinancialEntity]:
        raise NotImplementedError
