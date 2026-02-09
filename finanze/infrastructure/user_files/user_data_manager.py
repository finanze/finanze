import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from application.ports.data_manager import DataManager
from dateutil.tz import tzlocal
from domain.exception.exceptions import UserAlreadyExists
from domain.user import User, UserRegistration


class UserDataManager(DataManager):
    def __init__(self, base_path: str):
        self._base_path = base_path
        self._profiles_json_path = os.path.join(self._base_path, "profiles.json")
        self._profiles_dir = os.path.join(self._base_path, "profiles")

        os.makedirs(self._base_path, exist_ok=True)
        os.makedirs(self._profiles_dir, exist_ok=True)

        self._profiles_data: Dict[str, Any] = {}
        self._load_profiles()

        self._log = logging.getLogger(__name__)

    def _load_profiles(self):
        default_data = {"last_logged": None, "profiles": []}
        try:
            if (
                not os.path.exists(self._profiles_json_path)
                or os.path.getsize(self._profiles_json_path) == 0
            ):
                self._profiles_data = default_data
                self._save_profiles()
                return

            with open(self._profiles_json_path, "r") as f:
                data = json.load(f)

            if (
                isinstance(data, dict)
                and "last_logged" in data
                and "profiles" in data
                and isinstance(data["profiles"], list)
            ):
                self._profiles_data = data
            else:
                self._log.warning(
                    f"Warning: '{self._profiles_json_path}' is malformed. Initializing with default data."
                )
                self._profiles_data = default_data
                self._save_profiles()

        except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
            self._log.warning(
                f"Warning: Could not read/parse '{self._profiles_json_path}': {e}. Initializing with default data."
            )
            self._profiles_data = default_data
            if not os.path.exists(self._profiles_json_path):
                self._save_profiles()

    def _save_profiles(self):
        try:
            with open(self._profiles_json_path, "w") as f:
                json.dump(self._profiles_data, f, indent=4)
        except IOError as e:
            self._log.error(
                f"Error: Could not save profiles to '{self._profiles_json_path}': {e}"
            )

    def _profile_to_user(self, profile_data: Dict[str, Any]) -> User:
        user_id = uuid.UUID(profile_data["id"])
        last_login_dt = None
        if "last_logged" in profile_data:
            last_login_dt = datetime.fromisoformat(profile_data["last_logged"])

        return User(
            id=user_id,
            username=profile_data["name"],
            last_login=last_login_dt,
            path=Path(os.path.join(self._profiles_dir, str(user_id))),
        )

    async def get_last_user(self) -> Optional[User]:
        last_logged_id_str = self._profiles_data.get("last_logged")
        if not last_logged_id_str:
            return None

        for profile_dict in self._profiles_data.get("profiles", []):
            if profile_dict.get("id") == last_logged_id_str:
                return self._profile_to_user(profile_dict)

        return None

    async def set_last_user(self, user: User):
        user_id_str = str(user.id)
        self._profiles_data["last_logged"] = user_id_str

        for profile in self._profiles_data.get("profiles", []):
            if profile.get("id") == user_id_str:
                profile["last_logged"] = datetime.now(tzlocal()).isoformat()
                break

        self._save_profiles()

    async def get_users(self) -> List[User]:
        return [
            self._profile_to_user(p_data)
            for p_data in self._profiles_data.get("profiles", [])
        ]

    async def get_user(self, username: str) -> Optional[User]:
        for profile_data in self._profiles_data.get("profiles", []):
            if profile_data.get("name") == username:
                return self._profile_to_user(profile_data)
        return None

    async def create_user(self, user: UserRegistration) -> User:
        if self.get_user(user.username):
            raise UserAlreadyExists(
                f"User with username '{user.username}' already exists."
            )

        profile_data = {"id": str(user.id), "name": user.username}

        if "profiles" not in self._profiles_data or not isinstance(
            self._profiles_data["profiles"], list
        ):
            self._profiles_data["profiles"] = []

        self._profiles_data["profiles"].append(profile_data)

        user_profile_path = os.path.join(self._profiles_dir, str(user.id))
        os.makedirs(user_profile_path, exist_ok=True)

        self._save_profiles()

        return self._profile_to_user(profile_data)

    async def update_user(self, user: User):
        user_id_str = str(user.id)
        profile_found = False
        for profile in self._profiles_data.get("profiles", []):
            if profile.get("id") == user_id_str:
                profile["name"] = user.username
                profile["last_logged"] = user.last_login.isoformat()
                profile_found = True
                break

        if not profile_found:
            raise ValueError(f"User with ID '{user.id}' not found for update.")

        self._save_profiles()
