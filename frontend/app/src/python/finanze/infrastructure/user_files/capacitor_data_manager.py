import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from js import jsBridge

from application.ports.data_manager import DataManager
from domain.exception.exceptions import UserAlreadyExists
from domain.user import User, UserRegistration


class CapacitorSingleUserDataManager(DataManager):
    _USER_KEY = "user:single"

    async def get_last_user(self) -> Optional[User]:
        return await self._load_user()

    async def set_last_user(self, user: User):
        user.last_login = datetime.now().astimezone()
        await self._save_user(user)

    async def get_users(self) -> list[User]:
        user = await self._load_user()
        if user is None:
            return []
        return [user]

    async def get_user(self, username: str) -> Optional[User]:
        user = await self._load_user()
        if user and user.username == username:
            return user
        return None

    async def create_user(self, user: UserRegistration) -> User:
        existing = await self._load_user()
        if existing is not None:
            raise UserAlreadyExists(
                f"User with username '{existing.username}' already exists."
            )

        created = User(
            id=user.id,
            username=user.username,
            last_login=datetime.now().astimezone(),
            path=Path(f"/data/profiles/{user.id}"),
        )
        await self._save_user(created)
        return created

    async def update_user(self, user: User):
        await self._save_user(user)

    async def _load_user(self) -> Optional[User]:
        raw = await jsBridge.preferences.get(self._USER_KEY)
        if not raw:
            return None

        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                return None

            last_login_raw = parsed.get("last_login")
            last_login = (
                datetime.fromisoformat(last_login_raw) if last_login_raw else None
            )

            return User(
                id=UUID(parsed["id"]),
                username=parsed["username"],
                last_login=last_login,
                path=Path(parsed.get("path") or "/data"),
            )
        except Exception:
            return None

    async def _save_user(self, user: User):
        payload = {
            "id": str(user.id),
            "username": user.username,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "path": str(user.path),
        }
        await jsBridge.preferences.set(self._USER_KEY, json.dumps(payload))
