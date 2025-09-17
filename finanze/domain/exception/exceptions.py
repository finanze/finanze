from enum import Enum
from typing import Optional

from domain.external_integration import ExternalIntegrationId


class MissingFieldsError(Exception):
    def __init__(self, missing_fields: list[str]):
        self.missing_fields = missing_fields
        message = f"Missing required fields: {', '.join(missing_fields)}"
        super().__init__(message)


class FeatureNotSupported(Exception):
    pass


class EntityNotFound(Exception):
    pass


class ExternalIntegrationRequired(Exception):
    def __init__(self, required_integrations: list[ExternalIntegrationId]):
        self.required_integrations = required_integrations
        message = f"External Integrations required: {', '.join(required_integrations)}"
        super().__init__(message)


class UserNotFound(Exception):
    pass


class UserAlreadyLoggedIn(Exception):
    pass


class UserAlreadyExists(Exception):
    pass


class InvalidProvidedCredentials(Exception):
    pass


class NoAdapterFound(Exception):
    pass


class ExecutionConflict(Exception):
    pass


class AddressNotFound(Exception):
    pass


class AddressAlreadyExists(Exception):
    pass


class TooManyRequests(Exception):
    pass


class IntegrationSetupErrorCode(str, Enum):
    UNKNOWN = "UNKNOWN"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"


class IntegrationSetupError(Exception):
    def __init__(self, code: IntegrationSetupErrorCode):
        self.code = code
        super().__init__()


class RealEstateNotFound(Exception):
    pass


class FlowNotFound(Exception):
    pass


class ExportException(Exception):
    def __init__(self, details: str):
        self.details = details
        message = f"Error while exporting data: {details}"
        super().__init__(message)


class ExternalEntityLinkExpired(Exception):
    pass


class ExternalEntityFailed(Exception):
    pass


class ExternalEntityLinkError(Exception):
    def __init__(
        self, orphan_external_entity: bool = False, details: Optional[str] = None
    ):
        self.orphan_external_entity = orphan_external_entity
        self.details = details


class ExternalEntityNotFound(Exception):
    pass


class ProviderInstitutionNotFound(Exception):
    pass
