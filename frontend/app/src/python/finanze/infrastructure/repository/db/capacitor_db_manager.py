import asyncio
import hashlib
import logging
from asyncio import Lock
from datetime import datetime
from typing import Optional

from application.ports.datasource_backup_port import Backupable
from application.ports.datasource_initiator import DatasourceInitiator
from domain.data_init import (
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
from infrastructure.repository.db.settings_snapshot import (
    read_settings_rows,
    restore_settings_rows_if_empty,
)
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import get_schema_version, versions

try:
    import js  # type: ignore
except Exception:  # pragma: no cover
    js = None

try:
    from pyodide.ffi import to_js  # type: ignore
except Exception:  # pragma: no cover
    to_js = None

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
                return

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
                    self._unlocked = False
                    self._db_name = None
                    try:
                        await self._client.silent_close()
                    finally:
                        self._client.set_connection(None)
                    raise DecryptionError(
                        "Failed to decrypt database. Incorrect password or corrupted file"
                    ) from e

                if not isinstance(e, MigrationError):
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
            raise MigrationError(f"Database schema setup failed: {e}") from e

    async def export(self) -> bytes:
        if js is None:
            raise RuntimeError("Pyodide JS bridge is not available")

        await self._client.wal_checkpoint()
        await js.jsBridge.sqlite.exportDatabaseToStaging("EXPORTED_DATA")
        return b""

    @classmethod
    def _extract_ahead_of_time_migrations(cls, error: Exception) -> Optional[str]:
        msg = cls._stringify_error(error)
        marker = "MIGRATION_AHEAD_OF_TIME:"
        if marker not in msg:
            return None
        return msg.split(marker, 1)[1].split("\n", 1)[0].strip()

    async def _import_from_staging(
        self,
        db_name: str,
        password: str,
        known_migrations,
        delete_staging_file,
        delete_on_error: bool = False,
    ) -> None:
        import_err: Exception | None = None
        try:
            await js.jsBridge.sqlite.importDatabaseFromStaging(
                db_name, password, "DECOMPILED_DATA", known_migrations, delete_on_error
            )
        except Exception as e:
            import_err = e
            unknown_names = self._extract_ahead_of_time_migrations(e)
            if unknown_names is not None:
                raise MigrationAheadOfTime(
                    f"Database has migrations not present in this version: {unknown_names}"
                ) from e
            raise
        finally:
            try:
                await delete_staging_file("DECOMPILED_DATA")
            except Exception:
                if import_err is None:
                    raise
                self._log.warning(
                    "Could not delete staging file DECOMPILED_DATA after import error",
                    exc_info=True,
                )

    async def import_data(
        self,
        data: bytes,
        initialize: bool = False,
        user: Optional[User] = None,
        password: Optional[str] = None,
    ) -> None:
        if js is None:
            raise RuntimeError("Pyodide JS bridge is not available")

        from infrastructure.cloud.backup.capacitor_backup_processor import (
            delete_staging_file,
        )

        known_migrations = (
            to_js([m.name for m in versions])
            if to_js is not None
            else [m.name for m in versions]
        )

        if initialize:
            if user is None or password is None:
                raise RuntimeError("user and password are required for initial import")
            db_name = self._db_name_for_user(user)
            await self._import_from_staging(
                db_name,
                password,
                known_migrations,
                delete_staging_file,
                delete_on_error=True,
            )
            try:
                await self._initialize(
                    DatasourceInitParams.build(user=user, password=password)
                )
            except Exception:
                try:
                    await js.jsBridge.sqlite.deleteDatabase(db_name, password, True)
                except Exception:
                    self._log.warning(
                        "Could not delete broken initial database after upgrade failure",
                        exc_info=True,
                    )
                raise
            return

        user = self._user
        passwd = self._pass
        if user is None or passwd is None:
            raise RuntimeError("No active user/password available for import")

        db_name = self._db_name_for_user(user)

        settings_rows = await read_settings_rows(self._client)
        await js.jsBridge.sqlite.exportDatabaseToStaging("ROLLBACK_DATA")

        await self.lock()

        try:
            await self._import_from_staging(
                db_name, passwd, known_migrations, delete_staging_file
            )
            await self._initialize(
                DatasourceInitParams.build(user=user, password=passwd)
            )
        except Exception as e:
            main_untouched = isinstance(
                e, MigrationAheadOfTime
            ) or "CORRUPT_STAGING_DATABASE" in self._stringify_error(e)
            try:
                if not main_untouched:
                    await self.lock()
                    await js.jsBridge.sqlite.importDatabaseFromStaging(
                        db_name, passwd, "ROLLBACK_DATA"
                    )
                await self._initialize(
                    DatasourceInitParams.build(user=user, password=passwd)
                )
            except Exception as restore_err:
                self._log.exception(
                    "Could not restore database after failed import: %s",
                    restore_err,
                )
            raise
        finally:
            try:
                await delete_staging_file("ROLLBACK_DATA")
            except Exception:
                self._log.warning(
                    "Could not delete staging file ROLLBACK_DATA",
                    exc_info=True,
                )

        try:
            await restore_settings_rows_if_empty(self._client, settings_rows)
        except Exception as e:
            self._log.exception("Could not restore settings after import: %s", e)

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

    def get_version(self) -> int:
        return get_schema_version(versions)

    async def get_hashed_password(self) -> Optional[str]:
        if not self._unlocked:
            return None
        return hashlib.sha3_256(self._pass.encode("utf-8")).hexdigest()

    def get_user(self) -> Optional[User]:
        return self._user

    def set_user(self, user: User):
        self._user = user

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
