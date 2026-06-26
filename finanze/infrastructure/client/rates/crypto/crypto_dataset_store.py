from abc import ABC, abstractmethod
from typing import Optional

DATASET_FILENAMES = {
    "cg": "coingecko.json",
    "cmc": "cmc.json",
}


class CryptoDatasetStore(ABC):
    @abstractmethod
    async def load(self, key: str) -> Optional[str]:
        pass

    @abstractmethod
    async def save(self, key: str, raw_text: str) -> None:
        pass
