from domain.user import User
from pydantic.dataclasses import dataclass


class AlreadyUnlockedError(Exception):
    pass


class AlreadyLockedError(Exception):
    pass


class DecryptionError(Exception):
    pass


class DataEncryptedError(Exception):
    pass


class MigrationError(Exception):
    pass


@dataclass
class DatasourceInitParams:
    user: User
    password: str
