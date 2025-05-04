from pydantic.dataclasses import dataclass


class AlreadyUnlockedError(Exception):
    pass


class AlreadyLockedError(Exception):
    pass


class DecryptionError(Exception):
    pass


class DataEncryptedError(Exception):
    pass


@dataclass
class DatasourceInitParams:
    password: str
