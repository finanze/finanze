import abc
from datetime import date
from typing import Optional

from domain.gains_timeline import (
    AssetSnapshot,
    GainsAssetFilter,
    GainsFlow,
    GainsSettlement,
)


class GainsTimelinePort(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def get_asset_snapshots(
        self,
        assets: list[GainsAssetFilter],
        entity_ids: list[str],
        from_date: Optional[date] = None,
    ) -> list[AssetSnapshot]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_flows(
        self, assets: list[GainsAssetFilter], entity_ids: list[str]
    ) -> list[GainsFlow]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_settlements(
        self, assets: list[GainsAssetFilter], entity_ids: list[str]
    ) -> list[GainsSettlement]:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_data_version(self) -> str:
        raise NotImplementedError
