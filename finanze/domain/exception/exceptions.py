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


class EntityNameAlreadyExists(Exception):
    def __init__(self, name: str):
        super().__init__(f"Entity name already exists: {name}")


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


class TooManyRequests(Exception):
    pass


class IntegrationSetupErrorCode(str, Enum):
    UNKNOWN = "UNKNOWN"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"


class IntegrationSetupError(Exception):
    def __init__(self, code: IntegrationSetupErrorCode):
        self.code = code
        super().__init__()


class IntegrationNotFound(Exception):
    pass


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


class TransactionNotFound(Exception):
    pass


class RelatedAccountNotFound(Exception):
    def __init__(self, account_id):
        super().__init__(f"Related account not found: {account_id}")


class RelatedFundPortfolioNotFound(Exception):
    def __init__(self, portfolio_id):
        super().__init__(f"Related fund portfolio not found: {portfolio_id}")


class TemplateAlreadyExists(Exception):
    def __init__(self, name: str, template_type: str):
        super().__init__(f"Template '{name}' already exists for type {template_type}")


class TemplateNotFound(Exception):
    pass


class InvalidTemplateDefaultValue(Exception):
    def __init__(self, field_name: str, field_type: str, reason: str):
        super().__init__(
            f"Invalid default value for field '{field_name}' of type {field_type}: {reason}"
        )


class SheetNotFound(Exception):
    pass


class UnsupportedFileFormat(Exception):
    pass
