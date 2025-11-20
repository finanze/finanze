import abc

from domain.export import SheetParams
from domain.external_integration import ExternalIntegrationPayload


class SheetsPort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def update(
        self,
        table: list[list[str]],
        credentials: ExternalIntegrationPayload,
        params: SheetParams,
    ):
        raise NotImplementedError

    @abc.abstractmethod
    def read(
        self,
        credentials: ExternalIntegrationPayload,
        params: SheetParams,
    ) -> list[list[str]]:
        raise NotImplementedError
