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


class IntegrationSetupError(Exception):
    pass


class ExportException(Exception):
    def __init__(self, details: str):
        self.details = details
        message = f"Error while exporting data: {details}"
        super().__init__(message)
