import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

import jwt
from cachetools import TTLCache, cached, LRUCache
from cachetools.keys import hashkey
from jwt import DecodeError

from application.ports.backup_local_registry import BackupLocalRegistry
from application.ports.backup_settings_port import BackupSettingsPort
from application.ports.cloud_register import CloudRegister
from domain.backup import (
    BackupsInfo,
    BackupInfo,
    BackupFileType,
    BackupSettings,
    BackupMode,
)
from domain.cloud_auth import (
    CloudAuthToken,
    CloudAuthTokenData,
    CloudUserRole,
    CloudAuthData,
)
from domain.exception.exceptions import InvalidToken, NoUserLogged
from domain.user import User

CLOUD_DATA_FILE = "cloud.json"


class CloudDataRegister(CloudRegister, BackupLocalRegistry, BackupSettingsPort):
    def __init__(self):
        self._cloud_file = None
        self._log = logging.getLogger(__name__)

    def disconnect(self):
        self._log.debug("Disconnecting cloud data register")
        self._cloud_file = None
        if (
            hasattr(self._load_cloud_data, "cache")
            and hashkey(self) in self._load_cloud_data.cache
        ):
            del self._load_cloud_data.cache[hashkey(self)]

    def connect(self, user: User):
        self._log.debug("Connecting cloud data register")
        self._cloud_file = str(user.path / CLOUD_DATA_FILE)
        self._ensure_cloud_file_exists()

    def _check_connected(self):
        if not self._cloud_file:
            self._log.error("No user is currently logged in")
            raise NoUserLogged()

    def _ensure_cloud_file_exists(self):
        if not Path(self._cloud_file).is_file():
            self._log.debug(
                f"Cloud data file not found, creating default at {self._cloud_file}"
            )
            default_data = {"backup": {}, "auth": None}
            Path(self._cloud_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self._cloud_file, "w") as f:
                json.dump(default_data, f, indent=2)

    @cached(cache=TTLCache(maxsize=1, ttl=30))
    def _load_cloud_data(self) -> dict:
        self._check_connected()
        with open(self._cloud_file, "r") as f:
            return json.load(f)

    def _save_cloud_data(self, data: dict):
        self._check_connected()
        with open(self._cloud_file, "w") as f:
            json.dump(data, f, indent=2)

        # Update cache after saving
        key = hashkey(self)
        if hasattr(self._load_cloud_data, "cache"):
            self._load_cloud_data.cache[key] = data
        else:
            self._load_cloud_data.cache_clear()

    def get_info(self) -> BackupsInfo:
        self._check_connected()
        if not self._cloud_file or not Path(self._cloud_file).exists():
            return BackupsInfo(pieces={})

        cloud_data = self._load_cloud_data()
        backup_data = cloud_data.get("backup", {}).get("backups", {})

        backup_infos = {}
        for type_key, entry in backup_data.items():
            backup_type = BackupFileType(type_key)
            backup_info = BackupInfo(
                id=UUID(entry["id"]),
                protocol=entry["protocol"],
                date=datetime.fromisoformat(entry["date"]),
                type=backup_type,
                size=entry["size"],
            )
            backup_infos[backup_type] = backup_info

        return BackupsInfo(pieces=backup_infos)

    def insert(self, entries: list[BackupInfo]):
        self._check_connected()
        cloud_data = self._load_cloud_data()
        backup_section = cloud_data.get("backup", {})
        backups_data = backup_section.get("backups", {})

        for entry in entries:
            backups_data[entry.type.value] = {
                "id": str(entry.id),
                "protocol": entry.protocol,
                "date": entry.date.isoformat(),
                "size": entry.size,
            }

        backup_section["backups"] = backups_data
        cloud_data["backup"] = backup_section
        self._save_cloud_data(cloud_data)

        self._log.debug(
            f"Backup registry updated in cloud data file at {self._cloud_file}"
        )

    def save_auth(self, auth_token: CloudAuthToken):
        self._check_connected()
        cloud_data = self._load_cloud_data()
        token_dict = (
            {
                "token": {
                    "access_token": auth_token.access_token,
                    "refresh_token": auth_token.refresh_token,
                    "token_type": auth_token.token_type,
                    "expires_at": auth_token.expires_at,
                }
            }
            if auth_token
            else None
        )
        cloud_data["auth"] = token_dict
        self._save_cloud_data(cloud_data)
        self._log.debug("Auth token saved")

    def get_auth_token(self) -> Optional[CloudAuthToken]:
        self._check_connected()
        if not self._cloud_file or not Path(self._cloud_file).exists():
            return None
        cloud_data = self._load_cloud_data()
        token_dict = cloud_data.get("auth", {}).get("token")
        if not token_dict:
            return None
        return CloudAuthToken(
            access_token=token_dict.get("access_token"),
            refresh_token=token_dict.get("refresh_token"),
            token_type=token_dict.get("token_type"),
            expires_at=token_dict.get("expires_at"),
        )

    def get_auth(self) -> Optional[CloudAuthData]:
        token = self.get_auth_token()
        if token is None:
            return None
        auth_data = self.decode_token(token.access_token)
        return CloudAuthData(
            email=auth_data.email,
            role=auth_data.role,
            permissions=auth_data.permissions,
            token=token,
        )

    def clear_auth(self):
        self._check_connected()
        cloud_data = self._load_cloud_data()
        cloud_data["auth"] = None
        self._save_cloud_data(cloud_data)
        self._log.debug("Auth data cleared")

    @cached(cache=LRUCache(maxsize=2))
    def decode_token(self, token: str) -> Optional[CloudAuthTokenData]:
        try:
            payload = jwt.decode(
                token,
                options={"verify_signature": False},
            )

            role_str = payload.get("user_role")
            permissions = payload.get("permissions", [])
            email = payload.get("email")

            if not email:
                self._log.warning("Token missing 'email' claim")
                raise InvalidToken("Token missing required 'email' claim")

            if role_str:
                try:
                    role = CloudUserRole(role_str.upper())
                except ValueError:
                    self._log.warning(f"Invalid role value '{role_str}', using NONE")
                    role = CloudUserRole.NONE
            else:
                role = CloudUserRole.NONE

            if not isinstance(permissions, list):
                self._log.warning(
                    f"Permissions is not a list: {type(permissions)}, using empty list"
                )
                permissions = []

            self._log.debug(
                f"Token decoded successfully for email: {email}, role: {role}, permissions: {permissions}"
            )

            return CloudAuthTokenData(role=role, email=email, permissions=permissions)

        except DecodeError as e:
            self._log.warning(f"Token decode error: {e}")
            raise InvalidToken(f"Token is malformed: {str(e)}")

        except Exception as e:
            self._log.error(f"Unexpected error decoding token: {e}")
            raise InvalidToken(f"Error decoding token: {str(e)}")

    def get_backup_settings(self) -> BackupSettings:
        self._check_connected()
        cloud_data = self._load_cloud_data()
        backup_section = cloud_data.get("backup", {})
        settings_data = backup_section.get("settings", {})

        mode_str = settings_data.get("mode", "MANUAL")
        try:
            mode = BackupMode(mode_str)
        except ValueError:
            self._log.warning(f"Invalid backup mode '{mode_str}', using MANUAL")
            mode = BackupMode.MANUAL

        return BackupSettings(mode=mode)

    def save_backup_settings(self, settings: BackupSettings):
        self._check_connected()
        cloud_data = self._load_cloud_data()
        backup_section = cloud_data.get("backup", {})

        backup_section["settings"] = {"mode": settings.mode.value}

        cloud_data["backup"] = backup_section
        self._save_cloud_data(cloud_data)
        self._log.debug(f"Backup settings saved: mode={settings.mode.value}")
