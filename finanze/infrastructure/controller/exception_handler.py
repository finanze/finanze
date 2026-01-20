from quart import jsonify

from domain.data_init import DataEncryptedError
from domain.exception.exceptions import (
    AddressNotFound,
    BackupConflict,
    EntityNotFound,
    ExecutionConflict,
    ExternalIntegrationRequired,
    IntegrationNotFound,
    IntegrationSetupError,
    IntegrationSetupErrorCode,
    InvalidProvidedCredentials,
    InvalidTemplateDefaultValue,
    InvalidToken,
    TemplateNotFound,
    TooManyRequests,
    TransactionNotFound,
    UnauthorizedToken,
    NoUserLogged,
    PermissionDenied,
    InvalidUserCredentials,
)


def handle_unexpected_error(e):
    return {"code": "UNEXPECTED_ERROR", "message": str(e.original_exception)}, 500


def handle_invalid_authentication(e):
    return {"code": "INVALID_CREDENTIALS"}, 401


def handle_entity_not_found(e):
    return jsonify({"code": "ENTITY_NOT_FOUND", "message": str(e)}), 404


def handle_tx_not_found(e):
    return jsonify({"code": "TX_NOT_FOUND", "message": str(e)}), 404


def handle_invalid_credentials(e):
    return jsonify({"code": "INVALID_CREDENTIALS", "message": str(e)}), 400


def handle_user_not_logged(e):
    return jsonify({"code": "NOT_LOGGED"}), 401


def handle_value_error(e):
    return jsonify({"code": "INVALID_VALUE", "message": str(e)}), 400


def handle_execution_conflict(e):
    return jsonify({"code": "ALREADY_EXECUTING"}), 409


def handle_too_many_requests(e):
    return jsonify({"code": "TOO_MANY_REQUESTS"}), 429


def handle_address_not_found(e):
    return jsonify({"code": "ADDRESS_NOT_FOUND", "message": str(e)}), 404


def handle_integration_not_found(e):
    return jsonify({"code": "INTEGRATION_NOT_FOUND", "message": str(e)}), 404


def handle_integration_setup_error(e):
    if e.code == IntegrationSetupErrorCode.INVALID_CREDENTIALS:
        return jsonify({}), 401

    return jsonify({}), 500


def handle_required_integration(e: ExternalIntegrationRequired):
    return jsonify(
        {
            "code": "REQUIRED_INTEGRATION",
            "details": {"required": e.required_integrations},
        }
    ), 409


def handle_template_not_found(e):
    return jsonify({"code": "TEMPLATE_NOT_FOUND", "message": "Template not found"}), 404


def handle_invalid_template_default_value(e):
    return jsonify({"code": "INVALID_TEMPLATE_DEFAULT_VALUE", "message": str(e)}), 400


def handle_unauthorized_token(e):
    return jsonify(
        {"code": "UNAUTHORIZED_TOKEN", "message": "Token is invalid or expired"}
    ), 401


def handle_invalid_token(e):
    return jsonify({"code": "INVALID_TOKEN", "message": str(e)}), 400


def handle_backup_conflict(e):
    return jsonify({"code": "BACKUP_CONFLICT", "message": str(e)}), 409


def handle_permission_denied(e):
    return jsonify({"code": "PERMISSION_DENIED", "message": str(e)}), 403


def register_exception_handlers(app):
    app.register_error_handler(EntityNotFound, handle_entity_not_found)
    app.register_error_handler(TransactionNotFound, handle_tx_not_found)
    app.register_error_handler(InvalidProvidedCredentials, handle_invalid_credentials)
    app.register_error_handler(InvalidUserCredentials, handle_invalid_credentials)
    app.register_error_handler(DataEncryptedError, handle_user_not_logged)
    app.register_error_handler(NoUserLogged, handle_user_not_logged)
    app.register_error_handler(ExecutionConflict, handle_execution_conflict)
    app.register_error_handler(TooManyRequests, handle_too_many_requests)
    app.register_error_handler(AddressNotFound, handle_address_not_found)
    app.register_error_handler(IntegrationSetupError, handle_integration_setup_error)
    app.register_error_handler(IntegrationNotFound, handle_integration_not_found)
    app.register_error_handler(ExternalIntegrationRequired, handle_required_integration)
    app.register_error_handler(TemplateNotFound, handle_template_not_found)
    app.register_error_handler(
        InvalidTemplateDefaultValue, handle_invalid_template_default_value
    )
    app.register_error_handler(UnauthorizedToken, handle_unauthorized_token)
    app.register_error_handler(InvalidToken, handle_invalid_token)
    app.register_error_handler(BackupConflict, handle_backup_conflict)
    app.register_error_handler(PermissionDenied, handle_permission_denied)

    app.register_error_handler(500, handle_unexpected_error)
    app.register_error_handler(401, handle_invalid_authentication)
