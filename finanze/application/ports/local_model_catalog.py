import abc
from typing import Optional

from domain.local_model import LocalModelCatalogEntry


class LocalModelCatalog(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def entries(self) -> list[LocalModelCatalogEntry]:
        raise NotImplementedError

    def find(self, model_id: str) -> Optional[LocalModelCatalogEntry]:
        normalized = model_id.casefold()
        return next(
            (entry for entry in self.entries() if entry.id.casefold() == normalized),
            None,
        )
