import hashlib
import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from sqlite3 import Connection
from typing import Optional
from asyncio import Lock

from sqlcipher3 import dbapi2 as sqlcipher
from sqlcipher3._sqlite3 import DatabaseError

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
from infrastructure.repository.db.client import DBClient, UnderlyingConnection
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions

DB_NAME = "data.db"


class DBManager(DatasourceInitiator, Backupable):
    def __init__(self, db_client: DBClient):
        self._log = logging.getLogger(__name__)
        self._client = db_client
        self._lock = Lock()
        self._pass = None
        self._user: User | None = None
        self._unlocked = False

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
            await self._client.close()
            self._log.debug("Database locked successfully.")

    async def initialize(self, params: DatasourceInitParams):
        await self._initialize(params)

    async def _initialize(self, params: DatasourceInitParams) -> UnderlyingConnection:
        user_path = params.user.path

        user_db_path = user_path / DB_NAME
        self._log.info(f"Attempting to connect and unlock database at {user_db_path}")

        async with self._lock:
            if self._unlocked:
                self._log.info("Database is already unlocked")
                raise AlreadyUnlockedError()

            self._unlocked = False
            connection = None
            try:
                connection = self._base_connect(user_db_path)

                self._unlock_and_setup(connection, params.password)
                self._log.info("Database unlocked successfully")

                self._unlocked = True
                self._client.set_connection(connection)

                await self._setup_database_schema(params)
                self._pass = params.password
                self._user = params.user

                return connection

            except Exception as e:
                if isinstance(e, DatabaseError):
                    self._log.exception(f"Failed to unlock database: {e}")
                    if "file is not a database" in str(e) or "encrypted" in str(e):
                        raise DecryptionError(
                            "Failed to decrypt database. Incorrect password or corrupted file"
                        ) from e

                elif not isinstance(e, MigrationAheadOfTime):
                    self._log.exception(e)

                elif not isinstance(e, MigrationError):
                    self._log.exception(
                        "An unexpected error occurred during database connection/unlock"
                    )

                self._unlocked = False
                if connection:
                    connection.close()
                self._client.set_connection(None)
                raise

    @staticmethod
    def _base_connect(user_db_path: Path) -> Connection:
        connection = sqlcipher.connect(
            database=str(user_db_path),
            isolation_level=None,
            check_same_thread=False,
        )
        return connection

    @staticmethod
    def _sanitize_password(password: str) -> str:
        return password.replace(r"'", r"''")

    @staticmethod
    def _unlock_and_setup(connection: UnderlyingConnection, password: str):
        sanitized_pass = DBManager._sanitize_password(password)
        connection.execute(f"PRAGMA key='{sanitized_pass}';")

        connection.execute("SELECT count(*) FROM sqlite_master WHERE type='table';")

        connection.execute("PRAGMA journal_mode = WAL;")

        connection.execute("PRAGMA foreign_keys = ON;")
        connection.row_factory = sqlcipher.Row

        return connection

    async def change_password(
        self, user_params: DatasourceInitParams, new_password: str
    ):
        if not new_password:
            raise ValueError("New password cannot be empty")

        if self._unlocked:
            raise Exception(
                "Database is unlocked, it must be locked before changing password"
            )

        connection = await self._initialize(user_params)
        self._change_password(connection, new_password)
        await self.lock()

    def _change_password(self, connection: UnderlyingConnection, new_password: str):
        if not self._unlocked:
            raise Exception("Database must be unlocked before changing password")

        sanitized_pass = self._sanitize_password(new_password)
        connection.execute(f"PRAGMA rekey='{sanitized_pass}';")

        self._log.info("Database password changed successfully")

    async def _setup_database_schema(self, params: DatasourceInitParams):
        if not self._unlocked:
            raise Exception("Database must be unlocked before setting up schema")

        self._log.debug("Setting up database schema...")

        upgrader = DatabaseUpgrader(self._client, versions, params.context)

        try:
            await upgrader.upgrade()
            self._log.info("Database schema setup complete")
        except MigrationError:
            raise
        except Exception as e:
            raise MigrationError from e

    async def export(self) -> bytes:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()

        try:
            async with self._client.tx():
                # Update last update timestamp before exporting
                pass

            await self._client.wal_checkpoint()

            tmp_path_str = str(tmp_path.absolute())

            async with self._client.tx(skip_last_update=True) as cursor:
                await cursor.execute_script(f"""
                ATTACH DATABASE '{tmp_path_str}' AS backup_db KEY '';
                SELECT sqlcipher_export('backup_db');
                DETACH DATABASE backup_db;
                """)

            with open(tmp_path, "rb") as f:
                data = f.read()

            return data
        finally:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except (OSError, NameError):
                pass

    async def import_data(self, data: bytes):
        await self._client.wal_checkpoint()

        user = self._user
        user_path = user.path
        passwd = self._pass
        db_path = user_path / DB_NAME
        await self.lock()

        temp_old_db_path = user_path / (DB_NAME + ".tmp")
        shutil.copy2(db_path, temp_old_db_path)

        db_path.unlink()

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            tmp_bkg_db_path = Path(tmpdir) / "tmp_backup.db"
            tmp_bkg_db_path.write_bytes(data)

            connection = self._base_connect(tmp_bkg_db_path)
            temp_client = DBClient(connection)

            db_path_str = str(db_path.absolute())
            sanitized_passwd = self._sanitize_password(passwd)

            async with temp_client.tx(skip_last_update=True) as cursor:
                await cursor.execute_script(f"""
                ATTACH DATABASE '{db_path_str}' AS new_db KEY '{sanitized_passwd}';
                SELECT sqlcipher_export('new_db');
                DETACH DATABASE new_db;
                """)
            connection.close()

        await self._initialize(DatasourceInitParams(user=user, password=passwd))

        temp_old_db_path.unlink()

    async def get_last_updated(self) -> datetime:
        async with self._client.read() as cursor:
            await cursor.execute(
                """SELECT value
                   FROM sys_config
                   WHERE "key" = ?
                """,
                ("last_update",),
            )
            row = await cursor.fetchone()
            return datetime.fromisoformat(row["value"])

    async def get_hashed_password(self) -> Optional[str]:
        if not self._unlocked:
            return None

        return hashlib.sha3_256(self._pass.encode("utf-8")).hexdigest()

    def get_user(self) -> Optional[User]:
        return self._user
