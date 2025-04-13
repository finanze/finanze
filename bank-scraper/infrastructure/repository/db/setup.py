import os
import sqlite3

from pysqlcipher3 import dbapi2 as sqlcipher
from pathlib import Path
from typing import Union

from infrastructure.repository.db.client import DBClient
from infrastructure.repository.db.upgrader import DatabaseUpgrader
from infrastructure.repository.db.version_registry import versions


def initialize_database(path: Union[str, Path]) -> DBClient:
    #connection = sqlcipher.connect(
    connection = sqlite3.connect(
        database=str(path),
        isolation_level=None,
        check_same_thread=False,
    )

    #sqlcipher_pass = os.environ.get("DB_CIPHER_PASSWORD")
    #sqlcipher_pass = sqlcipher_pass.replace(r"'", r"''")
    #connection.execute(f"PRAGMA key='{sqlcipher_pass}';")

    connection.execute("PRAGMA foreign_keys = ON")

    connection.row_factory = sqlite3.Row

    client = DBClient(connection)

    upgrader = DatabaseUpgrader(client, versions)
    upgrader.upgrade()

    return client
