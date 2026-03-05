import json
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from domain.exception.exceptions import UserAlreadyExists
from domain.user import User, UserRegistration
from infrastructure.user_files.user_data_manager import UserDataManager

DEFAULT_PROFILES = {"last_logged": None, "profiles": []}


def _write_profiles_json(base: str, data):
    os.makedirs(base, exist_ok=True)
    os.makedirs(os.path.join(base, "profiles"), exist_ok=True)
    with open(os.path.join(base, "profiles.json"), "w") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f)


def _read_profiles_json(base: str) -> dict:
    with open(os.path.join(base, "profiles.json"), "r") as f:
        return json.load(f)


class TestInitialization:
    def test_creates_base_and_profiles_directories(self, tmp_path):
        base = str(tmp_path / "data")
        UserDataManager(base)
        assert os.path.isdir(base)
        assert os.path.isdir(os.path.join(base, "profiles"))

    def test_creates_default_profiles_json_in_empty_directory(self, tmp_path):
        base = str(tmp_path / "data")
        UserDataManager(base)
        data = _read_profiles_json(base)
        assert data == DEFAULT_PROFILES

    def test_loads_existing_valid_profiles_json(self, tmp_path):
        base = str(tmp_path)
        user_id = str(uuid4())
        existing = {
            "last_logged": user_id,
            "profiles": [{"id": user_id, "name": "alice"}],
        }
        _write_profiles_json(base, existing)
        manager = UserDataManager(base)
        assert manager._profiles_data == existing

    def test_malformed_json_missing_required_keys_resets_to_default(self, tmp_path):
        base = str(tmp_path)
        _write_profiles_json(base, {"some_key": "value"})
        manager = UserDataManager(base)
        assert manager._profiles_data == DEFAULT_PROFILES

    def test_malformed_json_profiles_not_a_list_resets_to_default(self, tmp_path):
        base = str(tmp_path)
        _write_profiles_json(base, {"last_logged": None, "profiles": "not_a_list"})
        manager = UserDataManager(base)
        assert manager._profiles_data == DEFAULT_PROFILES

    def test_invalid_json_syntax_resets_to_default(self, tmp_path):
        base = str(tmp_path)
        _write_profiles_json(base, "not json {{{")
        manager = UserDataManager(base)
        assert manager._profiles_data == DEFAULT_PROFILES

    def test_empty_file_resets_to_default(self, tmp_path):
        base = str(tmp_path)
        os.makedirs(base, exist_ok=True)
        os.makedirs(os.path.join(base, "profiles"), exist_ok=True)
        open(os.path.join(base, "profiles.json"), "w").close()
        manager = UserDataManager(base)
        assert manager._profiles_data == DEFAULT_PROFILES

    def test_json_array_instead_of_object_resets_to_default(self, tmp_path):
        base = str(tmp_path)
        _write_profiles_json(base, [1, 2, 3])
        manager = UserDataManager(base)
        assert manager._profiles_data == DEFAULT_PROFILES


class TestGetLastUser:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_last_logged(self, tmp_path):
        manager = UserDataManager(str(tmp_path))
        result = await manager.get_last_user()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_user_when_last_logged_is_set(self, tmp_path):
        base = str(tmp_path)
        user_id = uuid4()
        _write_profiles_json(
            base,
            {
                "last_logged": str(user_id),
                "profiles": [{"id": str(user_id), "name": "alice"}],
            },
        )
        manager = UserDataManager(base)
        result = await manager.get_last_user()
        assert result is not None
        assert result.id == user_id
        assert result.username == "alice"

    @pytest.mark.asyncio
    async def test_returns_none_when_last_logged_id_not_in_profiles(self, tmp_path):
        base = str(tmp_path)
        _write_profiles_json(
            base,
            {
                "last_logged": str(uuid4()),
                "profiles": [{"id": str(uuid4()), "name": "bob"}],
            },
        )
        manager = UserDataManager(base)
        result = await manager.get_last_user()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_user_with_last_login_datetime(self, tmp_path):
        base = str(tmp_path)
        user_id = uuid4()
        ts = "2025-06-15T10:30:00"
        _write_profiles_json(
            base,
            {
                "last_logged": str(user_id),
                "profiles": [{"id": str(user_id), "name": "alice", "last_logged": ts}],
            },
        )
        manager = UserDataManager(base)
        result = await manager.get_last_user()
        assert result.last_login == datetime.fromisoformat(ts)

    @pytest.mark.asyncio
    async def test_returns_user_with_none_last_login_when_no_timestamp(self, tmp_path):
        base = str(tmp_path)
        user_id = uuid4()
        _write_profiles_json(
            base,
            {
                "last_logged": str(user_id),
                "profiles": [{"id": str(user_id), "name": "alice"}],
            },
        )
        manager = UserDataManager(base)
        result = await manager.get_last_user()
        assert result.last_login is None


class TestSetLastUser:
    @pytest.mark.asyncio
    async def test_persists_last_logged_id(self, tmp_path):
        base = str(tmp_path)
        manager = UserDataManager(base)
        user_id = uuid4()
        created = await manager.create_user(
            UserRegistration(id=user_id, username="alice")
        )
        await manager.set_last_user(created)
        assert manager._profiles_data["last_logged"] == str(user_id)
        data = _read_profiles_json(base)
        assert data["last_logged"] == str(user_id)

    @pytest.mark.asyncio
    async def test_sets_last_logged_timestamp_on_matching_profile(self, tmp_path):
        base = str(tmp_path)
        manager = UserDataManager(base)
        user_id = uuid4()
        created = await manager.create_user(
            UserRegistration(id=user_id, username="alice")
        )
        await manager.set_last_user(created)
        profile = manager._profiles_data["profiles"][0]
        assert "last_logged" in profile
        datetime.fromisoformat(profile["last_logged"])

    @pytest.mark.asyncio
    async def test_updates_correct_profile_among_multiple(self, tmp_path):
        base = str(tmp_path)
        manager = UserDataManager(base)
        id_a = uuid4()
        id_b = uuid4()
        await manager.create_user(UserRegistration(id=id_a, username="alice"))
        created_b = await manager.create_user(UserRegistration(id=id_b, username="bob"))
        await manager.set_last_user(created_b)
        assert manager._profiles_data["last_logged"] == str(id_b)
        alice_profile = manager._profiles_data["profiles"][0]
        assert "last_logged" not in alice_profile
        bob_profile = manager._profiles_data["profiles"][1]
        assert "last_logged" in bob_profile


class TestGetUsers:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_users(self, tmp_path):
        manager = UserDataManager(str(tmp_path))
        users = await manager.get_users()
        assert users == []

    @pytest.mark.asyncio
    async def test_returns_all_created_users(self, tmp_path):
        manager = UserDataManager(str(tmp_path))
        await manager.create_user(UserRegistration(id=uuid4(), username="alice"))
        await manager.create_user(UserRegistration(id=uuid4(), username="bob"))
        await manager.create_user(UserRegistration(id=uuid4(), username="charlie"))
        users = await manager.get_users()
        assert len(users) == 3
        assert {u.username for u in users} == {"alice", "bob", "charlie"}

    @pytest.mark.asyncio
    async def test_returned_users_have_correct_paths(self, tmp_path):
        base = str(tmp_path)
        manager = UserDataManager(base)
        user_id = uuid4()
        await manager.create_user(UserRegistration(id=user_id, username="alice"))
        users = await manager.get_users()
        assert users[0].path == Path(os.path.join(base, "profiles", str(user_id)))


class TestGetUser:
    @pytest.mark.asyncio
    async def test_returns_user_when_found(self, tmp_path):
        manager = UserDataManager(str(tmp_path))
        user_id = uuid4()
        await manager.create_user(UserRegistration(id=user_id, username="alice"))
        found = await manager.get_user("alice")
        assert found is not None
        assert found.id == user_id
        assert found.username == "alice"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, tmp_path):
        manager = UserDataManager(str(tmp_path))
        found = await manager.get_user("nonexistent")
        assert found is None

    @pytest.mark.asyncio
    async def test_finds_correct_user_among_multiple(self, tmp_path):
        manager = UserDataManager(str(tmp_path))
        id_a = uuid4()
        id_b = uuid4()
        await manager.create_user(UserRegistration(id=id_a, username="alice"))
        await manager.create_user(UserRegistration(id=id_b, username="bob"))
        found = await manager.get_user("bob")
        assert found.id == id_b


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_returns_user_with_correct_fields(self, tmp_path):
        base = str(tmp_path)
        manager = UserDataManager(base)
        user_id = uuid4()
        user = await manager.create_user(UserRegistration(id=user_id, username="alice"))
        assert user.id == user_id
        assert user.username == "alice"
        assert user.last_login is None
        assert user.path == Path(os.path.join(base, "profiles", str(user_id)))

    @pytest.mark.asyncio
    async def test_creates_user_profile_directory(self, tmp_path):
        base = str(tmp_path)
        manager = UserDataManager(base)
        user_id = uuid4()
        await manager.create_user(UserRegistration(id=user_id, username="alice"))
        assert os.path.isdir(os.path.join(base, "profiles", str(user_id)))

    @pytest.mark.asyncio
    async def test_persists_user_to_profiles_json(self, tmp_path):
        base = str(tmp_path)
        manager = UserDataManager(base)
        user_id = uuid4()
        await manager.create_user(UserRegistration(id=user_id, username="alice"))
        data = _read_profiles_json(base)
        assert len(data["profiles"]) == 1
        assert data["profiles"][0]["id"] == str(user_id)
        assert data["profiles"][0]["name"] == "alice"

    @pytest.mark.asyncio
    async def test_raises_user_already_exists_on_duplicate_username(self, tmp_path):
        manager = UserDataManager(str(tmp_path))
        await manager.create_user(UserRegistration(id=uuid4(), username="alice"))
        with pytest.raises(UserAlreadyExists):
            await manager.create_user(UserRegistration(id=uuid4(), username="alice"))

    @pytest.mark.asyncio
    async def test_multiple_users_appended_to_profiles(self, tmp_path):
        base = str(tmp_path)
        manager = UserDataManager(base)
        await manager.create_user(UserRegistration(id=uuid4(), username="alice"))
        await manager.create_user(UserRegistration(id=uuid4(), username="bob"))
        data = _read_profiles_json(base)
        assert len(data["profiles"]) == 2


class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_updates_username_and_last_login(self, tmp_path):
        base = str(tmp_path)
        manager = UserDataManager(base)
        user_id = uuid4()
        created = await manager.create_user(
            UserRegistration(id=user_id, username="alice")
        )
        now = datetime(2025, 6, 15, 10, 30, 0)
        updated = User(
            id=user_id, username="alice_new", path=created.path, last_login=now
        )
        await manager.update_user(updated)
        profile = manager._profiles_data["profiles"][0]
        assert profile["name"] == "alice_new"
        assert profile["last_logged"] == now.isoformat()

    @pytest.mark.asyncio
    async def test_persists_update_to_file(self, tmp_path):
        base = str(tmp_path)
        manager = UserDataManager(base)
        user_id = uuid4()
        created = await manager.create_user(
            UserRegistration(id=user_id, username="alice")
        )
        now = datetime(2025, 1, 1, 12, 0, 0)
        updated = User(
            id=user_id, username="alice_v2", path=created.path, last_login=now
        )
        await manager.update_user(updated)
        data = _read_profiles_json(base)
        assert data["profiles"][0]["name"] == "alice_v2"
        assert data["profiles"][0]["last_logged"] == now.isoformat()

    @pytest.mark.asyncio
    async def test_updates_only_matching_user(self, tmp_path):
        base = str(tmp_path)
        manager = UserDataManager(base)
        id_a = uuid4()
        id_b = uuid4()
        await manager.create_user(UserRegistration(id=id_a, username="alice"))
        created_b = await manager.create_user(UserRegistration(id=id_b, username="bob"))
        now = datetime(2025, 3, 10, 8, 0, 0)
        updated = User(
            id=id_b, username="bob_updated", path=created_b.path, last_login=now
        )
        await manager.update_user(updated)
        assert manager._profiles_data["profiles"][0]["name"] == "alice"
        assert manager._profiles_data["profiles"][1]["name"] == "bob_updated"

    @pytest.mark.asyncio
    async def test_raises_value_error_when_user_not_found(self, tmp_path):
        manager = UserDataManager(str(tmp_path))
        unknown = User(
            id=uuid4(),
            username="ghost",
            path=Path("/tmp"),
            last_login=datetime(2025, 1, 1),
        )
        with pytest.raises(ValueError):
            await manager.update_user(unknown)

    @pytest.mark.asyncio
    async def test_updated_user_retrievable_by_new_name(self, tmp_path):
        manager = UserDataManager(str(tmp_path))
        user_id = uuid4()
        created = await manager.create_user(
            UserRegistration(id=user_id, username="alice")
        )
        now = datetime(2025, 6, 1, 9, 0, 0)
        updated = User(
            id=user_id, username="alice_renamed", path=created.path, last_login=now
        )
        await manager.update_user(updated)
        assert await manager.get_user("alice") is None
        found = await manager.get_user("alice_renamed")
        assert found is not None
        assert found.id == user_id
