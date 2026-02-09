import json
import logging
import base64
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from js import jsBridge

from application.ports.backup_local_registry import BackupLocalRegistry
from application.ports.backup_settings_port import BackupSettingsPort
from application.ports.cloud_register import CloudRegister
from domain.backup import (
    BackupInfo,
    BackupMode,
    BackupSettings,
    BackupsInfo,
    BackupFileType,
)
from domain.cloud_auth import (
    CloudAuthData,
    CloudAuthToken,
    CloudAuthTokenData,
    CloudUserRole,
)
from domain.exception.exceptions import InvalidToken, NoUserLogged
from domain.user import User


class CapacitorCloudDataRegister(
    CloudRegister, BackupLocalRegistry, BackupSettingsPort
):
    def __init__(self):
        self._log = logging.getLogger(__name__)
        self._prefs_key: Optional[str] = None
        self._cache: Optional[dict[str, Any]] = None

    async def connect(self, user: User):
        self._prefs_key = f"cloud:{user.hashed_id()}"
        await self._ensure_data_exists()

    async def disconnect(self):
        self._prefs_key = None
        self._cache = None

    def _check_connected(self):
        if not self._prefs_key:
            self._log.error("No user is currently logged in")
            raise NoUserLogged()

    async def _ensure_data_exists(self):
        self._check_connected()
        raw = await jsBridge.preferences.get(self._prefs_key)
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    self._cache = parsed
                    return
            except Exception:
                pass

        default_data: dict[str, Any] = {
            "backup": {"backups": {}, "settings": {}},
            "auth": None,
        }
        await jsBridge.preferences.set(self._prefs_key, json.dumps(default_data))
        self._cache = default_data

    async def _load_cloud_data(self) -> dict[str, Any]:
        self._check_connected()
        if self._cache is not None:
            return self._cache

        raw = await jsBridge.preferences.get(self._prefs_key)
        if not raw:
            await self._ensure_data_exists()
            return self._cache or {
                "backup": {"backups": {}, "settings": {}},
                "auth": None,
            }

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                self._cache = parsed
            else:
                self._cache = {"backup": {"backups": {}, "settings": {}}, "auth": None}
        except Exception:
            self._cache = {"backup": {"backups": {}, "settings": {}}, "auth": None}

        return self._cache

    async def _save_cloud_data(self, data: dict[str, Any]):
        self._check_connected()
        self._cache = data
        await jsBridge.preferences.set(self._prefs_key, json.dumps(data))

    async def get_info(self) -> BackupsInfo:
        cloud_data = await self._load_cloud_data()
        backup_data = (cloud_data.get("backup") or {}).get("backups") or {}

        backup_infos: dict[BackupFileType, BackupInfo] = {}
        for type_key, entry in backup_data.items():
            try:
                backup_type = BackupFileType(type_key)
                backup_info = BackupInfo(
                    id=UUID(entry["id"]),
                    protocol=int(entry["protocol"]),
                    date=datetime.fromisoformat(entry["date"]),
                    type=backup_type,
                    size=int(entry["size"]),
                )
                backup_infos[backup_type] = backup_info
            except Exception:
                continue

        return BackupsInfo(pieces=backup_infos)

    async def insert(self, entries: list[BackupInfo]):
        cloud_data = await self._load_cloud_data()
        backup_section = cloud_data.get("backup") or {}
        backups_data = backup_section.get("backups") or {}

        for entry in entries:
            backups_data[entry.type.value] = {
                "id": str(entry.id),
                "protocol": entry.protocol,
                "date": entry.date.isoformat(),
                "size": entry.size,
            }

        backup_section["backups"] = backups_data
        cloud_data["backup"] = backup_section
        await self._save_cloud_data(cloud_data)

    async def save_auth(self, token: CloudAuthToken):
        cloud_data = await self._load_cloud_data()
        cloud_data["auth"] = (
            {
                "token": {
                    "access_token": token.access_token,
                    "refresh_token": token.refresh_token,
                    "token_type": token.token_type,
                    "expires_at": token.expires_at,
                }
            }
            if token
            else None
        )
        await self._save_cloud_data(cloud_data)

    async def get_auth_token(self) -> Optional[CloudAuthToken]:
        cloud_data = await self._load_cloud_data()
        token_dict = (cloud_data.get("auth") or {}).get("token")
        if not token_dict:
            return None

        return CloudAuthToken(
            access_token=token_dict.get("access_token"),
            refresh_token=token_dict.get("refresh_token"),
            token_type=token_dict.get("token_type"),
            expires_at=token_dict.get("expires_at"),
        )

    async def get_auth(self) -> Optional[CloudAuthData]:
        token = await self.get_auth_token()
        if token is None:
            return None
        auth_data = await self.decode_token(token.access_token)
        return CloudAuthData(
            email=auth_data.email,
            role=auth_data.role,
            permissions=auth_data.permissions,
            token=token,
        )

    async def clear_auth(self):
        cloud_data = await self._load_cloud_data()
        cloud_data["auth"] = None
        await self._save_cloud_data(cloud_data)

    async def decode_token(self, token: str) -> Optional[CloudAuthTokenData]:
        try:
            payload = self._decode_jwt_payload(token)

            role_str = payload.get("user_role")
            permissions = payload.get("permissions", [])
            email = payload.get("email")

            if not email:
                self._log.warning("Token missing 'email' claim")
                raise InvalidToken("Token missing required 'email' claim")

            if role_str:
                try:
                    role = CloudUserRole(str(role_str).upper())
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

            return CloudAuthTokenData(role=role, email=email, permissions=permissions)

        except Exception as e:
            self._log.error(f"Unexpected error decoding token: {e}")
            raise InvalidToken(f"Error decoding token: {str(e)}")

    @staticmethod
    def _decode_jwt_payload(token: str) -> dict[str, Any]:
        parts = token.split(".")
        if len(parts) < 2:
            raise InvalidToken("Token is malformed")

        payload_b64 = parts[1]
        padding = "=" * ((4 - (len(payload_b64) % 4)) % 4)
        try:
            decoded = base64.urlsafe_b64decode(payload_b64 + padding)
            parsed = json.loads(decoded.decode("utf-8"))
        except Exception as e:
            raise InvalidToken("Token is malformed") from e

        if not isinstance(parsed, dict):
            raise InvalidToken("Token is malformed")
        return parsed

    async def get_backup_settings(self) -> BackupSettings:
        cloud_data = await self._load_cloud_data()
        backup_section = cloud_data.get("backup") or {}
        settings_data = backup_section.get("settings") or {}

        mode_str = settings_data.get("mode", "MANUAL")
        try:
            mode = BackupMode(mode_str)
        except ValueError:
            self._log.warning(f"Invalid backup mode '{mode_str}', using MANUAL")
            mode = BackupMode.MANUAL

        return BackupSettings(mode=mode)

    async def save_backup_settings(self, settings: BackupSettings):
        cloud_data = await self._load_cloud_data()
        backup_section = cloud_data.get("backup") or {}
        backup_section["settings"] = {"mode": settings.mode.value}
        cloud_data["backup"] = backup_section
        await self._save_cloud_data(cloud_data)
