from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional
from datetime import datetime


class CoinGeckoCacheStrategy(ABC):
    @abstractmethod
    async def load_coin_list(
        self,
    ) -> tuple[Optional[List[Dict[str, Any]]], Optional[datetime]]:
        pass

    @abstractmethod
    async def save_coin_list(self, data: List[Dict[str, Any]], last_updated: datetime):
        pass

    @abstractmethod
    async def load_platforms(
        self,
    ) -> tuple[Optional[List[Dict[str, Any]]], Optional[datetime]]:
        pass

    @abstractmethod
    async def save_platforms(self, data: List[Dict[str, Any]], last_updated: datetime):
        pass
