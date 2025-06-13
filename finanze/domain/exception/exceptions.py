from typing import List


class MissingFieldsError(Exception):
    def __init__(self, missing_fields: List[str]):
        self.missing_fields = missing_fields
        message = f"Missing required fields: {', '.join(missing_fields)}"
        super().__init__(message)


class FeatureNotSupported(Exception):
    pass


class EntityNotFound(Exception):
    pass


class UserNotFound(Exception):
    pass


class UserAlreadyExists(Exception):
    pass


class InvalidProvidedCredentials(Exception):
    pass


class NoAdapterFound(Exception):
    pass
