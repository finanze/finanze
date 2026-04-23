from dataclasses import dataclass
from typing import Any, Optional

from domain.user import User


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

    @staticmethod
    def build(
        user: User, password: str, context: Optional[DatasourceInitContext] = None
    ) -> "DatasourceInitParams":
        if context is None:
            context = DatasourceInitContext(config=None)
        return DatasourceInitParams(user=user, password=password, context=context)
