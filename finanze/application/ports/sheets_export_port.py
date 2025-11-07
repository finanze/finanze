import abc
from datetime import datetime
from typing import Optional

from domain.entity import Entity
from domain.external_integration import ExternalIntegrationPayload
from domain.settings import ProductSheetConfig


class SheetsUpdatePort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def update_sheet(
        self,
        data: object | dict[Entity, object],
        credentials: ExternalIntegrationPayload,
        config: ProductSheetConfig,
        last_update: Optional[dict[Entity, datetime]] = None,
    ):
        raise NotImplementedError
