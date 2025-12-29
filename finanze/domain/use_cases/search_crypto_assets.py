import abc

from domain.crypto import AvailableCryptoAssetsRequest, AvailableCryptoAssetsResult


class SearchCryptoAssets(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(
        self, request: AvailableCryptoAssetsRequest
    ) -> AvailableCryptoAssetsResult:
        raise NotImplementedError
