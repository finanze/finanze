from typing import Any, Optional

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


class MigrationAheadOfTime(MigrationError):
    pass


@dataclass
class DatasourceInitContext:
    config: Optional[Any]


@dataclass
class DatasourceInitParams:
    user: User
    password: str
    context: DatasourceInitContext
