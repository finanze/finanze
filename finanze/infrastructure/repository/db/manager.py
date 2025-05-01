import logging
from pathlib import Path
from threading import Lock

from pysqlcipher3 import dbapi2 as sqlcipher
from pysqlcipher3._sqlite3 import DatabaseError

from application.ports.datasource_initiator import DatasourceInitiator
from domain.data_init import DatasourceInitParams, DecryptionError, AlreadyUnlockedError
from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions


class DBManager(DatasourceInitiator):

    def __init__(self, db_client: DBClient, path: str | Path):
        self._log = logging.getLogger(__name__)
        self._client = db_client
        self._lock = Lock()
        self._unlocked = False
        self._path = path

    def initialize(self, params: DatasourceInitParams):
        self._log.info(f"Attempting to connect and unlock database at {self._path}")

        with self._lock:
            if self._unlocked:
                self._log.info("Database is already unlocked.")
                raise AlreadyUnlockedError()

            self._unlocked = False
            connection = None
            try:
                connection = sqlcipher.connect(
                    database=str(self._path),
                    isolation_level=None,
                    check_same_thread=False,
                )

                self._unlock_and_setup(connection, params.password)

                self._unlocked = True
                self._client.set_connection(connection)

            except DatabaseError as e:
                self._log.error(f"Failed to unlock database: {e}")
                if connection:
                    connection.close()
                if "file is not a database" in str(e) or "encrypted" in str(e):
                    raise DecryptionError("Failed to decrypt database. Incorrect password or corrupted file.") from e
                raise

            except Exception as e:
                self._log.exception("An unexpected error occurred during database connection/unlock.")
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

    def setup_database_schema(self):
        if not self._unlocked:
            raise ValueError("Database must be unlocked before setting up schema.")

        self._log.info("Setting up database schema...")

        upgrader = DatabaseUpgrader(self._client, versions)
        upgrader.upgrade()

        self._log.info("Database schema setup complete.")
