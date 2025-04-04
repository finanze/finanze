import sqlite3
from contextlib import contextmanager
from sqlite3 import IntegrityError
from types import TracebackType
from typing import Optional, Sequence, Literal, Any, Generator

from typing_extensions import TypeAlias, Self

UnderlyingCursor: TypeAlias = sqlite3.Cursor
UnderlyingConnection: TypeAlias = sqlite3.Connection


class DBCursor:

    def __init__(self, cursor: UnderlyingCursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> Self:
        return self

    def __exit__(
            self,
            exctype: Optional[BaseException],
            value: Optional[BaseException],
            traceback: Optional[TracebackType],
    ) -> Literal[False]:
        self.close()
        return False

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> Any:
        result = next(self._cursor, None)
        if result is None:
            raise StopIteration

        return result

    def execute(self, statement: str, *args) -> Self:
        return self._cursor.execute(statement, *args)

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchmany(self, size: Optional[int] = None) -> list[Any]:
        return self._cursor.fetchmany(size)

    def fetchall(self) -> list[Any]:
        return self._cursor.fetchall()

    def close(self) -> None:
        self._cursor.close()


class DBClient:

    def __init__(self, connection: UnderlyingConnection):
        self._conn = connection

    @contextmanager
    def tx(self) -> Generator[DBCursor, None, None]:
        cursor = self.cursor()
        cursor.execute('BEGIN TRANSACTION')
        try:
            yield cursor
        except IntegrityError:
            self.rollback()
            raise
        else:
            self.commit()
        finally:
            cursor.close()

    @contextmanager
    def read(self) -> Generator[DBCursor, None, None]:
        cursor = self.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def cursor(self) -> DBCursor:
        return DBCursor(self._conn.cursor())
