import abc

from domain.crypto import AvailableCryptoAssetsRequest, AvailableCryptoAssetsResult


class SearchCryptoAssets(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self, request: AvailableCryptoAssetsRequest
    ) -> AvailableCryptoAssetsResult:
        raise NotImplementedError
