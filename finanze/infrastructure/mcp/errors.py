import logging
from typing import Optional

from application.ports.error_reporter_port import ErrorReporterPort
from domain.data_init import DataEncryptedError
from domain.exception.exceptions import (
    AddressNotFound,
    CalculationInputError,
    EntityNotFound,
    ExecutionConflict,
    ExternalIntegrationRequired,
    ExternalLabelingUnavailable,
    FeatureNotSupported,
    FlowNotFound,
    InstrumentProviderUnavailable,
    IntegrationNotFound,
    IntegrationSetupError,
    InvalidBudgetLabel,
    InvalidLabelingRule,
    LabelingRuleNotFound,
    LabelNotFound,
    ManualAccountNotFound,
    MarketValueValuationRequired,
    MissingFieldsError,
    NoUserLogged,
    PermissionDenied,
    ProtectedLabel,
    RealEstateNotFound,
    RelatedAccountNotFound,
    RelatedFundPortfolioNotFound,
    TooManyRequests,
    TransactionNotFound,
)
from mcp.server.mcpserver.exceptions import ToolError

LOCKED_MESSAGE = (
    "Finanze is locked. Ask the user to open Finanze and log in, then retry."
)

_NOT_FOUND = {
    EntityNotFound: "Entity not found",
    TransactionNotFound: "Transaction not found",
    LabelNotFound: "Label not found",
    LabelingRuleNotFound: "Labeling rule not found",
    FlowNotFound: "Flow not found",
    RealEstateNotFound: "Real estate not found",
    AddressNotFound: "Address not found",
    IntegrationNotFound: "Integration not found",
    ManualAccountNotFound: "Account not found",
    RelatedAccountNotFound: "Related account not found",
    RelatedFundPortfolioNotFound: "Related fund portfolio not found",
}

_INVALID_INPUT = (
    ValueError,
    TypeError,
    KeyError,
    MissingFieldsError,
    CalculationInputError,
    MarketValueValuationRequired,
    FeatureNotSupported,
    InvalidBudgetLabel,
)

_log = logging.getLogger(__name__)


def _with_detail(prefix: str, error: Exception) -> str:
    detail = str(error).strip()
    return f"{prefix}: {detail}" if detail else prefix


def map_error(
    tool_name: str,
    error: Exception,
    error_reporter: Optional[ErrorReporterPort] = None,
) -> ToolError:
    if isinstance(error, (DataEncryptedError, NoUserLogged)):
        return ToolError(LOCKED_MESSAGE)
    for error_type, message in _NOT_FOUND.items():
        if isinstance(error, error_type):
            return ToolError(_with_detail(message, error))
    if isinstance(error, ProtectedLabel):
        return ToolError("This label is protected and cannot be changed.")
    if isinstance(error, InvalidLabelingRule):
        return ToolError(f"Invalid labeling rule: {error.details}")
    if isinstance(error, ExternalLabelingUnavailable):
        return ToolError(f"External labeling unavailable: {error.details}")
    if isinstance(error, ExecutionConflict):
        return ToolError(
            "The same operation is already running. Wait a moment and retry."
        )
    if isinstance(error, TooManyRequests):
        return ToolError("An external provider is rate limiting. Retry later.")
    if isinstance(error, ExternalIntegrationRequired):
        required = ", ".join(str(i.value) for i in error.required_integrations)
        return ToolError(
            f"This requires the following integrations to be connected: {required}"
        )
    if isinstance(error, IntegrationSetupError):
        return ToolError(f"Integration setup failed: {error.code.value}")
    if isinstance(error, PermissionDenied):
        return ToolError(_with_detail("Permission denied", error))
    if isinstance(error, InstrumentProviderUnavailable):
        return ToolError("The instrument data provider is unavailable. Retry later.")
    if isinstance(error, _INVALID_INPUT):
        return ToolError(_with_detail("Invalid input", error))

    _log.exception(f"Unexpected error in MCP tool {tool_name}", exc_info=error)
    if error_reporter:
        error_reporter.capture_exception(error, tags={"mcp_tool": tool_name})
    return ToolError(
        "Unexpected error. Check the Finanze logs for details and retry later."
    )
