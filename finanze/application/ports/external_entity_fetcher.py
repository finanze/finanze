import abc

from domain.exception.exceptions import FeatureNotSupported
from domain.external_entity import (
    ExternalEntityConnectionResult,
    ExternalEntityFetchRequest,
    ExternalEntityLoginRequest,
    ExternalEntityProviderIntegrations,
    ProviderExternalEntityDetails,
)
from domain.global_position import GlobalPosition


class ExternalEntityFetcher(metaclass=abc.ABCMeta):
    def setup(self, credentials: ExternalEntityProviderIntegrations):
        raise NotImplementedError

    async def create_or_link(
        self, request: ExternalEntityLoginRequest
    ) -> ExternalEntityConnectionResult:
        raise NotImplementedError

    async def unlink(self, provider_instance_id: str):
        raise NotImplementedError

    async def is_linked(self, provider_instance_id: str) -> bool:
        raise NotImplementedError

    async def get_entity(
        self, provider_entity_id: str
    ) -> ProviderExternalEntityDetails:
        raise NotImplementedError

    async def get_entities(self, **kwargs) -> list[ProviderExternalEntityDetails]:
        raise NotImplementedError

    async def global_position(
        self, request: ExternalEntityFetchRequest
    ) -> GlobalPosition:
        raise FeatureNotSupported
