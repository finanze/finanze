from enum import Enum

from pydantic.dataclasses import dataclass

from domain.exception.exceptions import PermissionDenied, NoUserLogged


@dataclass
class CloudAuthToken:
    access_token: str
    refresh_token: str
    token_type: str
    expires_at: int


@dataclass
class CloudAuthRequest:
    token: CloudAuthToken | None


class CloudUserRole(str, Enum):
    NONE = "NONE"
    PLUS = "PLUS"


@dataclass
class CloudAuthResponse:
    role: CloudUserRole | None
    permissions: list[str] | None


@dataclass
class CloudAuthTokenData:
    email: str
    role: CloudUserRole
    permissions: list[str]


@dataclass
class CloudAuthData:
    role: CloudUserRole
    permissions: list[str]
    token: CloudAuthToken
    email: str


class CloudPermission(str, Enum):
    BACKUP_INFO = "backup.info"
    BACKUP_CREATE = "backup.create"
    BACKUP_IMPORT = "backup.import"

    def check(self, auth: CloudAuthData) -> None:
        if auth.permissions is None:
            raise NoUserLogged()
        permissions = auth.permissions or []
        if self.value not in permissions:
            raise PermissionDenied(self.value)
