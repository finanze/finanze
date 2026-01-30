import asyncio
import hashlib
import logging
from asyncio import Lock
from datetime import datetime
from typing import Optional

from application.ports.datasource_backup_port import Backupable
from application.ports.datasource_initiator import DatasourceInitiator
from domain.data_init import (
    AlreadyLockedError,
    AlreadyUnlockedError,
    DatasourceInitParams,
    DecryptionError,
    MigrationAheadOfTime,
    MigrationError,
)
from domain.user import User
from infrastructure.repository.db.capacitor_client import (
    CapacitorDBClient,
    UnderlyingConnection,
)
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions

import js

DB_NAME = "data.db"
DEFAULT_JS_TIMEOUT_SECONDS = 20


class CapacitorDBManager(DatasourceInitiator, Backupable):
    def __init__(self, db_client: CapacitorDBClient):
        self._log = logging.getLogger(__name__)
        self._client = db_client
        self._lock = Lock()
        self._pass = None
        self._user: User | None = None
        self._unlocked = False
        self._db_name: str | None = None

    @property
    def unlocked(self) -> bool:
        return self._unlocked

    async def lock(self):
        async with self._lock:
            if not self._unlocked:
                self._log.warning("Database is already locked.")
                raise AlreadyLockedError()

            self._unlocked = False
            self._user = None
            self._pass = None
            self._db_name = None
            await self._client.close()
            self._log.debug("Database locked successfully.")

    async def initialize(self, params: DatasourceInitParams):
        return await self._initialize(params)

    async def _initialize(self, params: DatasourceInitParams) -> UnderlyingConnection:
        if js is None:
            raise RuntimeError("Pyodide JS bridge is not available")

        async with self._lock:
            if self._unlocked:
                self._log.info("Database is already unlocked")
                raise AlreadyUnlockedError()

            self._unlocked = False
            connection: UnderlyingConnection | None = None

            try:
                db_name = self._db_name_for_user(params.user)
                self._log.info("Opening database %s", db_name)

                connection = await self._await_js(
                    f"sqlite.openDatabase({db_name})",
                    js.jsBridge.sqlite.openDatabase(
                        db_name,
                        True,
                        "secret",
                        1,
                        False,
                        params.password,
                    ),
                )

                self._log.info("Database connection opened: %s", db_name)

                await self._unlock_and_setup(params.password)

                self._client.set_connection(connection)
                self._unlocked = True

                await self._setup_database_schema(params)

                self._pass = params.password
                self._user = params.user
                self._db_name = db_name

                return connection

            except Exception as e:
                msg = self._stringify_error(e)
                if self._looks_like_decryption_error(msg):
                    raise DecryptionError(
                        "Failed to decrypt database. Incorrect password or corrupted file"
                    ) from e

                if isinstance(e, MigrationAheadOfTime):
                    raise
                if isinstance(e, MigrationError):
                    raise

                self._log.exception("Failed to unlock database: %s", e)
                self._unlocked = False
                self._db_name = None
                try:
                    await self._client.silent_close()
                finally:
                    self._client.set_connection(None)
                raise

    @staticmethod
    def _stringify_error(error: Exception) -> str:
        parts: list[str] = []
        try:
            parts.append(str(error))
        except Exception:
            parts.append(repr(error))

        try:
            args = getattr(error, "args", None)
            if args:
                parts.extend([str(a) for a in args if a is not None])
        except Exception:
            pass

        js_error = getattr(error, "js_error", None)
        if js_error is not None:
            for attr in ("message", "errorMessage", "stack"):
                try:
                    val = getattr(js_error, attr, None)
                    if val:
                        parts.append(str(val))
                except Exception:
                    pass

        return "\n".join([p for p in parts if p])

    async def _await_js(
        self,
        label: str,
        awaitable,
        timeout_seconds: int = DEFAULT_JS_TIMEOUT_SECONDS,
    ):
        self._log.info("DB init step: %s", label)
        try:
            return await asyncio.wait_for(awaitable, timeout=timeout_seconds)
        except asyncio.TimeoutError as e:
            self._log.error(
                "DB init timed out during %s after %ss", label, timeout_seconds
            )
            raise RuntimeError(
                f"Timeout during database initialization step: {label}"
            ) from e

    @staticmethod
    def _db_name_for_user(user: User) -> str:
        return f"{user.hashed_id()}_{DB_NAME}"

    @staticmethod
    def _sanitize_password(password: str) -> str:
        return password.replace(r"'", r"''")

    async def _unlock_and_setup(self, password: str) -> None:
        if js is None:
            raise RuntimeError("Pyodide JS bridge is not available")

        await self._await_js(
            "sqlite.setEncryptionKey",
            js.jsBridge.sqlite.setEncryptionKey(password),
            timeout_seconds=10,
        )

        try:
            await self._await_js(
                "sqlite.querySql(decryption-check)",
                js.jsBridge.sqlite.querySql(
                    "SELECT count(*) AS c FROM sqlite_master WHERE type='table'",
                    [],
                ),
                timeout_seconds=10,
            )
        except Exception as e:
            raise DecryptionError("Failed to decrypt database") from e

        await self._await_js(
            "sqlite.executeSql(PRAGMA journal_mode=WAL)",
            js.jsBridge.sqlite.executeSql("PRAGMA journal_mode = WAL", []),
            timeout_seconds=10,
        )
        await self._await_js(
            "sqlite.executeSql(PRAGMA foreign_keys=ON)",
            js.jsBridge.sqlite.executeSql("PRAGMA foreign_keys = ON", []),
            timeout_seconds=10,
        )

    async def change_password(
        self, user_params: DatasourceInitParams, new_password: str
    ):
        if not new_password:
            raise ValueError("New password cannot be empty")

        if self._unlocked:
            raise Exception(
                "Database is unlocked, it must be locked before changing password"
            )

        await self._initialize(user_params)
        await self._change_password(new_password)
        await self.lock()

    async def _change_password(self, new_password: str):
        if not self._unlocked:
            raise Exception("Database must be unlocked before changing password")

        if js is None:
            raise RuntimeError("Pyodide JS bridge is not available")

        sanitized_pass = self._sanitize_password(new_password)
        await js.jsBridge.sqlite.executeSql(f"PRAGMA rekey='{sanitized_pass}'", [])

        self._log.info("Database password changed successfully")

    async def _setup_database_schema(self, params: DatasourceInitParams):
        if not self._unlocked:
            raise Exception("Database must be unlocked before setting up schema")

        upgrader = DatabaseUpgrader(self._client, versions, params.context)
        try:
            await upgrader.upgrade()
        except MigrationError:
            raise
        except Exception as e:
            raise MigrationError from e

    async def export(self) -> bytes:
        if js is None:
            raise RuntimeError("Pyodide JS bridge is not available")

        await self._client.wal_checkpoint()
        await js.jsBridge.sqlite.exportDatabaseToStaging("EXPORTED_DATA")
        return b""

    async def import_data(self, data: bytes) -> None:
        if js is None:
            raise RuntimeError("Pyodide JS bridge is not available")

        from infrastructure.cloud.backup.capacitor_backup_processor import (
            delete_staging_file,
        )

        user = self._user
        passwd = self._pass
        if user is None or passwd is None:
            raise RuntimeError("No active user/password available for import")

        db_name = self._db_name_for_user(user)

        await self.lock()

        await js.jsBridge.sqlite.importDatabaseFromStaging(
            db_name, passwd, "DECOMPILED_DATA"
        )
        await delete_staging_file("DECOMPILED_DATA")
        await self._initialize(DatasourceInitParams.build(user=user, password=passwd))

    async def get_last_updated(self) -> datetime:
        if not self._unlocked:
            return datetime.min

        async with self._client.read() as cursor:
            await cursor.execute(
                """SELECT value FROM sys_config WHERE "key" = ?""",
                ("last_update",),
            )
            row = await cursor.fetchone()
            if row and row["value"]:
                try:
                    return datetime.fromisoformat(row["value"])
                except Exception:
                    return datetime.min
            return datetime.min

    async def get_hashed_password(self) -> Optional[str]:
        if not self._unlocked:
            return None
        return hashlib.sha3_256(self._pass.encode("utf-8")).hexdigest()

    def get_user(self) -> Optional[User]:
        return self._user

    @staticmethod
    def _looks_like_decryption_error(message: str) -> bool:
        msg = (message or "").lower()
        return any(
            token in msg
            for token in (
                "not a database",
                "file is encrypted",
                "encrypted",
                "sqlcipher",
                "wrong key",
                "malformed",
                "hmac check failed",
                "cannot open the db",
                "openorcreatedatabase",
            )
        )
