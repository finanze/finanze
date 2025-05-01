from pydantic.dataclasses import dataclass


class AlreadyUnlockedError(Exception):
    pass


class DecryptionError(Exception):
    pass


@dataclass
class DatasourceInitParams:
    password: str
