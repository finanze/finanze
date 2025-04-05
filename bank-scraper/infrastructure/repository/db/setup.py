import sqlite3
from pathlib import Path
from typing import Union

from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions


def initialize_database(path: Union[str, Path]) -> DBClient:
    connection = sqlite3.connect(
        database=str(path),
        isolation_level=None,
        check_same_thread=False,
    )

    connection.execute("PRAGMA foreign_keys = ON")

    connection.row_factory = sqlite3.Row

    client = DBClient(connection)

    upgrader = DatabaseUpgrader(client, versions)
    upgrader.upgrade()

    return client
