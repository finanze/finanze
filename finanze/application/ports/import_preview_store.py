import abc
from typing import Optional

from domain.importing import ImportPreview


class ImportPreviewStore(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def save(self, preview: ImportPreview) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def take(self, token: str) -> Optional[ImportPreview]:
        raise NotImplementedError

    @abc.abstractmethod
    def clear(self):
        raise NotImplementedError
