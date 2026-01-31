import abc

from domain.crypto import CryptoAssetDetails
from domain.external_integration import ExternalIntegrationId


class GetCryptoAssetDetails(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def execute(
        self, provider_id: str, provider: ExternalIntegrationId
    ) -> CryptoAssetDetails:
        raise NotImplementedError
