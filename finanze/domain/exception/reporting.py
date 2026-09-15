import asyncio

from domain.data_init import DataEncryptedError
from domain.exception.exceptions import (
    AddressNotFound,
    BackupConflict,
    BackupTransferFailed,
    CalculationInputError,
    EntityNameAlreadyExists,
    EntityNotFound,
    ExecutionConflict,
    ExportException,
    ExternalEntityFailed,
    ExternalEntityLinkError,
    ExternalEntityLinkExpired,
    ExternalEntityNotFound,
    ExternalIntegrationRequired,
    ExternalProviderAppNotLinked,
    FeatureNotSupported,
    FlowNotFound,
    IntegrationNotFound,
    IntegrationSetupError,
    InvalidBackupCredentials,
    InvalidPassword,
    InvalidProvidedCredentials,
    InvalidTemplateDefaultValue,
    InvalidToken,
    InvalidUserCredentials,
    InvalidUsername,
    ManualAccountNotFound,
    ManualHistoricEntryNotFinal,
    ManualHistoricEntryNotFound,
    ManualInvestmentNotFound,
    MarketValueValuationRequired,
    MissingFieldsError,
    NoUserLogged,
    PermissionDenied,
    ProviderInstitutionNotFound,
    RealEstateNotFound,
    RelatedAccountNotFound,
    RelatedFundPortfolioNotFound,
    SheetNotFound,
    TemplateAlreadyExists,
    TemplateNotFound,
    TooManyRequests,
    TransactionNotFound,
    UnauthorizedToken,
    UnsupportedBackupProtocol,
    UnsupportedFileFormat,
    UserAlreadyExists,
    UserAlreadyLoggedIn,
    UserNotFound,
)

# Expected outcomes of a business flow: surfaced to the user, never a defect.
EXPECTED_EXCEPTIONS: tuple[type[BaseException], ...] = (
    AddressNotFound,
    BackupConflict,
    BackupTransferFailed,
    CalculationInputError,
    DataEncryptedError,
    EntityNameAlreadyExists,
    EntityNotFound,
    ExecutionConflict,
    ExportException,
    ExternalEntityFailed,
    ExternalEntityLinkError,
    ExternalEntityLinkExpired,
    ExternalEntityNotFound,
    ExternalIntegrationRequired,
    ExternalProviderAppNotLinked,
    FeatureNotSupported,
    FlowNotFound,
    IntegrationNotFound,
    IntegrationSetupError,
    InvalidBackupCredentials,
    InvalidPassword,
    InvalidProvidedCredentials,
    InvalidTemplateDefaultValue,
    InvalidToken,
    InvalidUserCredentials,
    InvalidUsername,
    ManualAccountNotFound,
    ManualHistoricEntryNotFinal,
    ManualHistoricEntryNotFound,
    ManualInvestmentNotFound,
    MarketValueValuationRequired,
    MissingFieldsError,
    NoUserLogged,
    PermissionDenied,
    ProviderInstitutionNotFound,
    RealEstateNotFound,
    RelatedAccountNotFound,
    RelatedFundPortfolioNotFound,
    SheetNotFound,
    TemplateAlreadyExists,
    TemplateNotFound,
    TooManyRequests,
    TransactionNotFound,
    UnauthorizedToken,
    UnsupportedBackupProtocol,
    UnsupportedFileFormat,
    UserAlreadyExists,
    UserAlreadyLoggedIn,
    UserNotFound,
    ValueError,
)

CONTROL_FLOW_EXCEPTIONS: tuple[type[BaseException], ...] = (
    asyncio.CancelledError,
    KeyboardInterrupt,
    SystemExit,
    GeneratorExit,
)

# Connectivity failures depend on the user's network, not on our code.
_NETWORK_MODULES = frozenset(
    {"httpx", "httpcore", "urllib3", "requests", "aiohttp", "socket", "ssl", "h2"}
)

_NETWORK_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
)


def is_reportable(exc: BaseException) -> bool:
    if isinstance(exc, CONTROL_FLOW_EXCEPTIONS):
        return False

    if isinstance(exc, EXPECTED_EXCEPTIONS):
        return False

    if isinstance(exc, _NETWORK_EXCEPTIONS):
        return False

    root_module = type(exc).__module__.split(".")[0]
    return root_module not in _NETWORK_MODULES
