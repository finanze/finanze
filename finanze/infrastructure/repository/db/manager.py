import logging
from pathlib import Path
from threading import Lock

from application.ports.datasource_initiator import DatasourceInitiator
from domain.data_init import (
    AlreadyLockedError,
    AlreadyUnlockedError,
    DatasourceInitParams,
    DecryptionError,
)
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions
from pysqlcipher3 import dbapi2 as sqlcipher
from pysqlcipher3._sqlite3 import DatabaseError

DB_NAME = "data.db"


class DBManager(DatasourceInitiator):
    def __init__(self, db_client: DBClient):
        self._log = logging.getLogger(__name__)
        self._client = db_client
        self._lock = Lock()
        self._unlocked = False

    @property
    def unlocked(self) -> bool:
        return self._unlocked

    def lock(self):
        with self._lock:
            if not self._unlocked:
                self._log.info("Database is already locked.")
                raise AlreadyLockedError()

            self._unlocked = False
            self._client.close()

    def initialize(self, params: DatasourceInitParams):
        user_path = Path(params.user.path) / DB_NAME
        self._log.info(f"Attempting to connect and unlock database at {user_path}")

        with self._lock:
            if self._unlocked:
                self._log.info("Database is already unlocked.")
                raise AlreadyUnlockedError()

            self._unlocked = False
            connection = None
            try:
                connection = sqlcipher.connect(
                    database=str(user_path),
                    isolation_level=None,
                    check_same_thread=False,
                )

                self._unlock_and_setup(connection, params.password)

                self._unlocked = True
                self._client.set_connection(connection)

                self._setup_database_schema()

            except DatabaseError as e:
                self._log.error(f"Failed to unlock database: {e}")
                if connection:
                    connection.close()
                if "file is not a database" in str(e) or "encrypted" in str(e):
                    raise DecryptionError(
                        "Failed to decrypt database. Incorrect password or corrupted file."
                    ) from e
                raise

            except Exception:
                self._log.exception(
                    "An unexpected error occurred during database connection/unlock."
                )
                if connection:
                    connection.close()
                raise

    def _unlock_and_setup(self, connection: sqlcipher.Connection, password: str):
        sanitized_pass = password.replace(r"'", r"''")
        connection.execute(f"PRAGMA key='{sanitized_pass}';")

        connection.execute("SELECT count(*) FROM sqlite_master WHERE type='table';")

        self._log.info("Database unlocked successfully.")

        connection.execute("PRAGMA foreign_keys = ON;")
        connection.row_factory = sqlcipher.Row

        return connection

    def _setup_database_schema(self):
        if not self._unlocked:
            raise ValueError("Database must be unlocked before setting up schema.")

        self._log.info("Setting up database schema...")

        upgrader = DatabaseUpgrader(self._client, versions)
        upgrader.upgrade()

        self._log.info("Database schema setup complete.")
