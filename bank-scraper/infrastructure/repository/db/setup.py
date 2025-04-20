import os
from pathlib import Path
from typing import Union

from pysqlcipher3 import dbapi2 as sqlcipher

from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions


def initialize_database(path: Union[str, Path]) -> DBClient:
    connection = sqlcipher.connect(
        database=str(path),
        isolation_level=None,
        check_same_thread=False,
    )

    sqlcipher_pass = os.environ.get("DB_CIPHER_PASSWORD")
    sqlcipher_pass = sqlcipher_pass.replace(r"'", r"''")
    connection.execute(f"PRAGMA key='{sqlcipher_pass}';")

    connection.execute("PRAGMA foreign_keys = ON;")

    connection.row_factory = sqlcipher.Row

    client = DBClient(connection)

    upgrader = DatabaseUpgrader(client, versions)
    upgrader.upgrade()

    return client
