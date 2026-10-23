from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
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


class NoUserLogged(Exception):
    pass


class UserNotFound(Exception):
    pass


class InvalidUserCredentials(Exception):
    pass


class UserAlreadyLoggedIn(Exception):
    pass


class UserAlreadyExists(Exception):
    pass


class InvalidUsername(Exception):
    pass


class InvalidPassword(Exception):
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
    def __init__(self, completed=None):
        self.completed = completed


class ExternalProviderAppNotLinked(Exception):
    pass


class IntegrationSetupErrorCode(str, Enum):
    UNKNOWN = "UNKNOWN"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    INVALID_PRIVATE_KEY = "INVALID_PRIVATE_KEY"
    INVALID_URL = "INVALID_URL"
    UNREACHABLE = "UNREACHABLE"
    NOT_A_MODEL_ROUTER = "NOT_A_MODEL_ROUTER"
    MISSING_SERVER_URL = "MISSING_SERVER_URL"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    AUTHORIZATION_EXPIRED = "AUTHORIZATION_EXPIRED"


INTEGRATION_SETUP_UNAUTHORIZED_CODES = (
    IntegrationSetupErrorCode.INVALID_CREDENTIALS,
    IntegrationSetupErrorCode.INVALID_PRIVATE_KEY,
)
INTEGRATION_SETUP_BAD_REQUEST_CODES = (
    IntegrationSetupErrorCode.INVALID_URL,
    IntegrationSetupErrorCode.NOT_A_MODEL_ROUTER,
    IntegrationSetupErrorCode.MISSING_SERVER_URL,
    IntegrationSetupErrorCode.AUTHORIZATION_DENIED,
    IntegrationSetupErrorCode.AUTHORIZATION_EXPIRED,
)


class IntegrationSetupError(Exception):
    def __init__(self, code: IntegrationSetupErrorCode):
        self.code = code
        super().__init__()


class IntegrationNotFound(Exception):
    pass


class AIProviderErrorCode(str, Enum):
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    UNAVAILABLE = "UNAVAILABLE"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"


class AIProviderError(Exception):
    def __init__(self, code: AIProviderErrorCode, details: str):
        self.code = code
        self.details = details
        super().__init__(details)


class LocalModelErrorCode(str, Enum):
    MISSING_SERVER_URL = "MISSING_SERVER_URL"
    INVALID_URL = "INVALID_URL"
    UNREACHABLE = "UNREACHABLE"
    UNAUTHORIZED = "UNAUTHORIZED"
    NOT_A_MODEL_ROUTER = "NOT_A_MODEL_ROUTER"
    SERVER_ERROR = "SERVER_ERROR"
    RUNTIME_FAILED = "RUNTIME_FAILED"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    INVALID_MODEL = "INVALID_MODEL"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    NOT_DELETABLE = "NOT_DELETABLE"
    INSUFFICIENT_SPACE = "INSUFFICIENT_SPACE"
    IMPORT_UNSUPPORTED = "IMPORT_UNSUPPORTED"
    INVALID_FILE = "INVALID_FILE"
    HUGGING_FACE_UNAVAILABLE = "HUGGING_FACE_UNAVAILABLE"
    HUGGING_FACE_REPO_NOT_FOUND = "HUGGING_FACE_REPO_NOT_FOUND"
    UNSUPPORTED_MODEL = "UNSUPPORTED_MODEL"


class LocalModelError(Exception):
    def __init__(self, code: LocalModelErrorCode, details: Optional[str] = None):
        self.code = code
        self.details = details or code.value
        super().__init__(self.details)


class RealEstateNotFound(Exception):
    pass


class ManualInvestmentNotFound(Exception):
    def __init__(self, entry_id):
        super().__init__(f"Manual investment not found: {entry_id}")


class ManualHistoricEntryNotFound(Exception):
    def __init__(self, entry_id):
        super().__init__(f"Manual historic entry not found: {entry_id}")


class ManualHistoricEntryNotFinal(Exception):
    def __init__(self, entry_id):
        super().__init__(f"Manual historic entry is not settled: {entry_id}")


class MarketValueValuationRequired(Exception):
    def __init__(self):
        super().__init__("At least one valuation must be marked as market value")


class FlowNotFound(Exception):
    pass


class ManualAccountNotFound(Exception):
    def __init__(self, account_id):
        super().__init__(f"Manual account not found: {account_id}")


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


class LabelNotFound(Exception):
    pass


class ProtectedLabel(Exception):
    pass


class InvalidBudgetLabel(Exception):
    pass


class LabelingRuleNotFound(Exception):
    pass


class InvalidLabelingRule(Exception):
    def __init__(self, details: str):
        self.details = details
        super().__init__(details)


class ExternalLabelingUnavailable(Exception):
    def __init__(self, details: str):
        self.details = details
        super().__init__(details)


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


class CalculationInputError(Exception):
    def __init__(self, details: str):
        self.details = details
        super().__init__(details)


class InvalidBackupCredentials(Exception):
    pass


class BackupConflict(Exception):
    """Raised when local changes conflict with remote backup"""

    pass


class BackupTransferFailed(Exception):
    """Raised when backup upload or download to cloud storage fails"""

    pass


class UnsupportedBackupProtocol(Exception):
    def __init__(self, protocol_version: int):
        super().__init__(f"Unsupported backup protocol version: {protocol_version}")


class UnauthorizedToken(Exception):
    """Raised when a token is invalid or expired"""

    pass


class InvalidToken(Exception):
    """Raised when a token cannot be decoded or is malformed"""

    pass


class PermissionDenied(Exception):
    pass


class InstrumentProviderUnavailable(Exception):
    """Raised when a price provider failed, so a missing quote proves nothing"""

    pass
